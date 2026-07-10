from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from router.core.contracts import TaskEnvelope
from router.orchestration.fireworks_model_router import (
    _build_candidates,
    _task_profile,
    rank_fireworks_models,
    select_reasoning_effort,
)


FEATURE_NAMES = [
    "bias",
    "tier_cheap",
    "tier_strong",
    "domain_formatting",
    "domain_classification",
    "domain_math_reasoning",
    "domain_logic",
    "domain_summarization",
    "domain_extraction",
    "domain_code_debug",
    "domain_code_generation",
    "domain_current_factual",
    "shape_exact_output",
    "shape_json_output",
    "shape_json_numeric",
    "shape_json_extraction",
    "shape_constrained_summary",
    "shape_direct_numeric",
    "shape_word_problem",
    "shape_structured_extraction",
    "shape_code_fix",
    "shape_code_generate",
    "shape_syllogism",
    "shape_ordering_logic",
    "shape_short_answer",
    "capability",
    "correlation",
    "reliability",
    "cost_utility",
    "token_utility",
    "latency_utility",
    "nash_product",
    "prisoner_payoff",
    "family_gpt_oss",
    "family_deepseek",
    "family_minimax",
    "family_kimi",
    "family_qwen",
    "interaction_minimax_math",
    "interaction_minimax_code_debug",
    "interaction_minimax_code_generation",
    "interaction_minimax_extraction",
    "interaction_kimi_math",
    "interaction_kimi_code_debug",
    "interaction_kimi_code_generation",
    "interaction_kimi_extraction",
    "reasoning_none",
    "reasoning_low",
    "reasoning_medium",
    "reasoning_omitted",
]

MIN_EMPIRICAL_GATE_CALLS = 8
EMPIRICAL_ACCURACY_GATE = 0.60


@dataclass(frozen=True)
class RegressionTask:
    id: str
    prompt: str
    domain: str | None = None
    tier: str | None = None


@dataclass(frozen=True)
class MatrixRegressionWeights:
    feature_names: list[str]
    coefficients: list[float]
    ridge_lambda: float
    training_rows: int
    target_mean: float
    observed_models: list[str] | None = None
    domain_model_stats: dict[str, dict[str, dict[str, float]]] | None = None

    def predict(self, features: list[float]) -> float:
        return sum(coefficient * value for coefficient, value in zip(self.coefficients, features))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MatrixRegressionWeights":
        return cls(
            feature_names=list(payload["feature_names"]),
            coefficients=[float(value) for value in payload["coefficients"]],
            ridge_lambda=float(payload["ridge_lambda"]),
            training_rows=int(payload["training_rows"]),
            target_mean=float(payload["target_mean"]),
            observed_models=[str(value) for value in payload.get("observed_models") or []] or None,
            domain_model_stats=_coerce_domain_model_stats(payload.get("domain_model_stats")),
        )


def fit_matrix_regression(
    rows: list[dict[str, Any]],
    tasks: dict[str, RegressionTask],
    *,
    allowed_models: list[str] | None = None,
    ridge_lambda: float = 0.35,
) -> MatrixRegressionWeights:
    if not rows:
        raise ValueError("Cannot fit matrix regression without rows.")
    models = allowed_models or sorted({str(row["model"]) for row in rows})
    token_bounds = _bounds(_row_token_total(row) for row in rows)
    latency_bounds = _bounds(float(row.get("latency_ms") or 0.0) for row in rows)
    matrix: list[list[float]] = []
    targets: list[float] = []
    observed_models: set[str] = set()
    stats_accumulator: dict[str, dict[str, dict[str, float]]] = {}
    for row in rows:
        task = tasks.get(str(row["id"]))
        if task is None:
            continue
        candidate = _candidate_for_training_row(row, task, models)
        if candidate is None:
            continue
        observed_models.add(candidate.model)
        tier = task.tier or _task_profile(task.prompt).tier
        domain = _normalize_domain(task.domain or _task_profile(task.prompt).domain)
        reasoning_effort = _row_reasoning_effort(row)
        _add_domain_model_stat(stats_accumulator, _domain_shape_key(domain, task.prompt), candidate.model, row)
        _add_domain_model_stat(stats_accumulator, domain, candidate.model, row)
        _add_domain_model_stat(stats_accumulator, "__overall__", candidate.model, row)
        matrix.append(_feature_vector(candidate, tier, domain, reasoning_effort, task.prompt))
        targets.append(_target(row, token_bounds, latency_bounds))
    if not matrix:
        raise ValueError("No trainable rows matched the provided tasks.")
    coefficients = _ridge_regression(matrix, targets, ridge_lambda)
    return MatrixRegressionWeights(
        feature_names=FEATURE_NAMES,
        coefficients=coefficients,
        ridge_lambda=ridge_lambda,
        training_rows=len(matrix),
        target_mean=sum(targets) / len(targets),
        observed_models=sorted(observed_models),
        domain_model_stats=_finalize_domain_model_stats(stats_accumulator),
    )


def select_model_by_matrix_regression(
    task: TaskEnvelope,
    allowed_models: list[str],
    weights: MatrixRegressionWeights,
) -> dict[str, Any]:
    task_profile = _task_profile(task.input_text)
    normalized_models = rank_fireworks_models(allowed_models)
    observed_allowed_models = _observed_allowed_models(normalized_models, weights)
    if observed_allowed_models:
        normalized_models = observed_allowed_models
    candidates = _build_candidates(normalized_models, task_profile)
    chat_candidates = [candidate for candidate in candidates if candidate.supports_chat]
    if not chat_candidates:
        raise ValueError("No chat-capable Fireworks model available in ALLOWED_MODELS.")
    eligible = [
        candidate
        for candidate in chat_candidates
        if candidate.capability >= task_profile.required_capability
    ]
    pool = eligible or chat_candidates
    prepared = []
    for candidate in pool:
        empirical = _empirical_stats_for(weights, task_profile.domain, candidate.model, task.input_text)
        predicted_total_tokens = _predicted_total_tokens(candidate.estimated_total_tokens, empirical)
        prepared.append((candidate, empirical, predicted_total_tokens))
    token_bounds = _bounds(predicted_total_tokens for _, _, predicted_total_tokens in prepared)
    scored = []
    for candidate, empirical, predicted_total_tokens in prepared:
        reasoning_effort = select_reasoning_effort(candidate.model, task_profile.tier)
        features = _feature_vector(candidate, task_profile.tier, task_profile.domain, reasoning_effort, task.input_text)
        regression_score = weights.predict(features)
        regression_utility = _clamp(regression_score, 0.0, 1.0)
        score_weights = _hybrid_score_weights(task_profile.tier)
        empirical_utility = empirical["valid_rate_smoothed"]
        empirical_confidence = empirical["confidence"]
        empirical_wilson_lower = _wilson_lower(
            int(empirical["valid"]),
            int(empirical["calls"]),
        )
        accuracy_feasible = (
            empirical["calls"] < MIN_EMPIRICAL_GATE_CALLS
            or empirical_wilson_lower >= EMPIRICAL_ACCURACY_GATE
        )
        predicted_token_utility = _inverse_range(predicted_total_tokens, *token_bounds)
        base_hybrid_score = (
            (score_weights["regression"] * regression_utility)
            + (score_weights["nash"] * candidate.nash_product)
            + (score_weights["token"] * predicted_token_utility)
            + (score_weights["cost"] * candidate.cost_utility)
        )
        hybrid_score = _risk_adjusted_score(base_hybrid_score, empirical_utility, empirical_confidence)
        scored.append(
            {
                "model": candidate.model,
                "regression_score": regression_score,
                "regression_utility": regression_utility,
                "base_hybrid_score": base_hybrid_score,
                "hybrid_score": hybrid_score,
                "hybrid_score_weights": score_weights,
                "nash_product": candidate.nash_product,
                "estimated_total_tokens": candidate.estimated_total_tokens,
                "token_utility": candidate.token_utility,
                "predicted_total_tokens": predicted_total_tokens,
                "predicted_token_utility": predicted_token_utility,
                "estimated_cost_usd": candidate.estimated_cost_usd,
                "empirical_valid_rate": empirical["valid_rate"],
                "empirical_valid_rate_smoothed": empirical_utility,
                "empirical_confidence": empirical_confidence,
                "empirical_calls": empirical["calls"],
                "empirical_wilson_lower_95": empirical_wilson_lower,
                "accuracy_feasible": accuracy_feasible,
                "empirical_avg_total_tokens": empirical["avg_total_tokens"],
                "features": dict(zip(FEATURE_NAMES, features)),
            }
        )
    feasible = [row for row in scored if row["accuracy_feasible"]] or scored
    selected = max(
        feasible,
        key=lambda row: (
            row["hybrid_score"],
            -row["predicted_total_tokens"],
            -row["estimated_cost_usd"],
            row["model"],
        ),
    )
    return {
        "model": selected["model"],
        "selection_rule": "matrix_regression_plus_nash",
        "tier": task_profile.tier,
        "domain": task_profile.domain,
        "accuracy_gate": EMPIRICAL_ACCURACY_GATE,
        "accuracy_gate_minimum_calls": MIN_EMPIRICAL_GATE_CALLS,
        "accuracy_gate_fallback_used": not any(row["accuracy_feasible"] for row in scored),
        "observed_model_filter": weights.observed_models,
        "ranked_candidates": sorted(
            scored,
            key=lambda row: (
                row["accuracy_feasible"],
                row["hybrid_score"],
                -row["predicted_total_tokens"],
                -row["estimated_cost_usd"],
                row["model"],
            ),
            reverse=True,
        ),
    }


def load_microbench_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def load_regression_tasks(path: Path) -> dict[str, RegressionTask]:
    tasks: dict[str, RegressionTask] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        tasks[str(payload["id"])] = RegressionTask(
            id=str(payload["id"]),
            prompt=str(payload["prompt"]),
            domain=str(payload.get("domain") or "") or None,
            tier=str(payload.get("tier") or "") or None,
        )
    return tasks


def save_weights(weights: MatrixRegressionWeights, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(weights.to_dict(), ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_weights(path: Path) -> MatrixRegressionWeights:
    return MatrixRegressionWeights.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _observed_allowed_models(models: list[str], weights: MatrixRegressionWeights) -> list[str]:
    observed = set(weights.observed_models or [])
    if not observed:
        return []
    filtered = [model for model in models if model in observed]
    return filtered if filtered else []


def _candidate_for_training_row(
    row: dict[str, Any],
    task: RegressionTask,
    models: list[str],
) -> Any | None:
    task_profile = _task_profile(task.prompt)
    if task.domain or task.tier:
        task_profile = replace(
            task_profile,
            domain=task.domain or task_profile.domain,
            tier=task.tier or task_profile.tier,
        )
    candidates = _build_candidates(models, task_profile)
    model = str(row["model"])
    for candidate in candidates:
        if candidate.model == model:
            return candidate
    return None


def _feature_vector(candidate: Any, tier: str, domain: str, reasoning_effort: str | None, prompt: str = "") -> list[float]:
    family = _model_family(candidate.model)
    reasoning = reasoning_effort or "omitted"
    domain = _normalize_domain(domain)
    shape = _prompt_shape(prompt)
    return [
        1.0,
        1.0 if tier == "cheap" else 0.0,
        1.0 if tier == "strong" else 0.0,
        1.0 if domain == "formatting" else 0.0,
        1.0 if domain == "classification" else 0.0,
        1.0 if domain == "math_reasoning" else 0.0,
        1.0 if domain == "logic" else 0.0,
        1.0 if domain == "summarization" else 0.0,
        1.0 if domain == "extraction" else 0.0,
        1.0 if domain == "code_debug" else 0.0,
        1.0 if domain == "code_generation" else 0.0,
        1.0 if domain == "current_factual" else 0.0,
        shape["exact_output"],
        shape["json_output"],
        shape["json_numeric"],
        shape["json_extraction"],
        shape["constrained_summary"],
        shape["direct_numeric"],
        shape["word_problem"],
        shape["structured_extraction"],
        shape["code_fix"],
        shape["code_generate"],
        shape["syllogism"],
        shape["ordering_logic"],
        shape["short_answer"],
        min(candidate.capability / 4.0, 1.0),
        candidate.correlation,
        candidate.reliability,
        0.0,  # Dollar price is intentionally excluded from the competition score.
        candidate.token_utility,
        candidate.latency_utility,
        candidate.nash_product,
        candidate.prisoner_payoff,
        1.0 if family == "gpt_oss" else 0.0,
        1.0 if family == "deepseek" else 0.0,
        1.0 if family == "minimax" else 0.0,
        1.0 if family == "kimi" else 0.0,
        1.0 if family == "qwen" else 0.0,
        1.0 if family == "minimax" and domain == "math_reasoning" else 0.0,
        1.0 if family == "minimax" and domain == "code_debug" else 0.0,
        1.0 if family == "minimax" and domain == "code_generation" else 0.0,
        1.0 if family == "minimax" and domain == "extraction" else 0.0,
        1.0 if family == "kimi" and domain == "math_reasoning" else 0.0,
        1.0 if family == "kimi" and domain == "code_debug" else 0.0,
        1.0 if family == "kimi" and domain == "code_generation" else 0.0,
        1.0 if family == "kimi" and domain == "extraction" else 0.0,
        1.0 if reasoning == "none" else 0.0,
        1.0 if reasoning == "low" else 0.0,
        1.0 if reasoning == "medium" else 0.0,
        1.0 if reasoning == "omitted" else 0.0,
    ]


def _prompt_shape(prompt: str) -> dict[str, float]:
    lowered = prompt.lower()
    word_count = len(re.findall(r"\b\w+\b", prompt))
    direct_numeric = bool(
        re.search(r"\d", lowered)
        and (
            re.search(r"\b(compute|calculate|evaluate)\b", lowered)
            or re.search(r"\b(min|max|minimum|maximum|mean|median|sum|total|product)\b", lowered)
            or re.search(r"\d+\s*[-+*/]\s*\d+", lowered)
        )
    )
    word_problem = bool(
        re.search(r"\d", lowered)
        and (
            re.search(r"\bhow\s+(many|much)\b", lowered)
            or re.search(r"\b(percent|percentage|rate|average|discount|fee|per hour|ratio)\b", lowered)
        )
    )
    structured_extraction = bool(re.search(r"\b(extract|return only the title|invoice|date|amount|email|url|phone|named entit)", lowered))
    constrained_summary = bool(re.search(r"\bsummari[sz]e\b", lowered) and "include" in lowered and re.search(r"\bat most\s+\d+\s+words?\b", lowered))
    json_output = bool(re.search(r"\b(json|minified)\b", lowered))
    return {
        "exact_output": 1.0 if re.search(r"\b(return only|return exactly|nothing else|exactly this string)\b", lowered) else 0.0,
        "json_output": 1.0 if json_output else 0.0,
        "json_numeric": 1.0 if json_output and direct_numeric else 0.0,
        "json_extraction": 1.0 if json_output and structured_extraction else 0.0,
        "constrained_summary": 1.0 if constrained_summary else 0.0,
        "direct_numeric": 1.0 if direct_numeric else 0.0,
        "word_problem": 1.0 if word_problem else 0.0,
        "structured_extraction": 1.0 if structured_extraction else 0.0,
        "code_fix": 1.0 if re.search(r"\b(debug|fix|bug|traceback|corrected)\b", lowered) else 0.0,
        "code_generate": 1.0 if re.search(r"\b(write|create|define|implement)\b.{0,80}\b(function|class|method|script|program|python code|javascript code|typescript code)\b", lowered) else 0.0,
        "syllogism": 1.0 if re.search(r"\b(all|some|no)\s+[a-z][a-z0-9_-]*s?\s+(are|is)\b", lowered) else 0.0,
        "ordering_logic": 1.0 if re.search(r"\b(shortest|tallest|smallest|largest|youngest|oldest|lightest|heaviest)\b", lowered) else 0.0,
        "short_answer": 1.0 if word_count <= 32 else 0.0,
    }


def _domain_shape_key(domain: str, prompt: str) -> str:
    return f"{_normalize_domain(domain)}::{_shape_signature(prompt)}"


def _shape_signature(prompt: str) -> str:
    shape = _prompt_shape(prompt)
    if shape["json_numeric"]:
        return "json_numeric"
    if shape["json_extraction"]:
        return "json_extraction"
    if shape["constrained_summary"]:
        return "constrained_summary"
    if shape["word_problem"]:
        return "word_problem"
    if shape["direct_numeric"]:
        return "direct_numeric"
    if shape["code_fix"]:
        return "code_fix"
    if shape["code_generate"]:
        return "code_generate"
    if shape["structured_extraction"]:
        return "structured_extraction"
    if shape["syllogism"]:
        return "syllogism"
    if shape["ordering_logic"]:
        return "ordering_logic"
    if shape["json_output"]:
        return "json"
    if shape["exact_output"]:
        return "exact"
    if shape["short_answer"]:
        return "short_answer"
    return "general"


def _hybrid_score_weights(tier: str) -> dict[str, float]:
    if tier == "strong":
        return {"regression": 0.80, "nash": 0.10, "token": 0.10, "cost": 0.00}
    if tier == "medium":
        return {"regression": 0.65, "nash": 0.15, "token": 0.20, "cost": 0.00}
    return {"regression": 0.50, "nash": 0.20, "token": 0.30, "cost": 0.00}


def _target(
    row: dict[str, Any],
    token_bounds: tuple[float, float],
    latency_bounds: tuple[float, float],
) -> float:
    valid = bool(row.get("valid"))
    token_utility = _inverse_range(_row_token_total(row), *token_bounds)
    latency_utility = _inverse_range(float(row.get("latency_ms") or 0.0), *latency_bounds)
    return (0.80 if valid else 0.0) + (0.18 * token_utility) + (0.02 * latency_utility)


def _row_token_total(row: dict[str, Any]) -> float:
    usage = row.get("usage")
    if isinstance(usage, dict):
        return float(usage.get("total") or 0.0)
    return float(row.get("total_tokens") or row.get("tokens") or 0.0)


def _row_reasoning_effort(row: dict[str, Any]) -> str | None:
    options = row.get("request_options")
    if isinstance(options, dict):
        value = options.get("reasoning_effort")
        if isinstance(value, str):
            return value
    return None


def _normalize_domain(domain: str) -> str:
    aliases = {
        "sentiment": "classification",
        "sentiment_classification": "classification",
        "ner": "extraction",
        "named_entity_recognition": "extraction",
        "code_debugging": "code_debug",
        "debugging": "code_debug",
        "logic_puzzles": "logic",
        "logical_reasoning": "logic",
        "factual_qa": "current_factual",
        "factual": "current_factual",
    }
    return aliases.get(domain, domain)


def _model_family(model: str) -> str:
    lowered = model.lower()
    if "gpt-oss" in lowered:
        return "gpt_oss"
    if "deepseek" in lowered:
        return "deepseek"
    if "minimax" in lowered:
        return "minimax"
    if "kimi" in lowered:
        return "kimi"
    if "qwen" in lowered:
        return "qwen"
    return "other"


def _add_domain_model_stat(
    accumulator: dict[str, dict[str, dict[str, float]]],
    domain: str,
    model: str,
    row: dict[str, Any],
) -> None:
    stats = accumulator.setdefault(domain, {}).setdefault(
        model,
        {
            "calls": 0.0,
            "valid": 0.0,
            "tokens": 0.0,
            "cost": 0.0,
            "latency_ms": 0.0,
        },
    )
    stats["calls"] += 1.0
    stats["valid"] += 1.0 if row.get("valid") else 0.0
    stats["tokens"] += _row_token_total(row)
    stats["cost"] += float(row.get("estimated_cost_usd") or 0.0)
    stats["latency_ms"] += float(row.get("latency_ms") or 0.0)


def _finalize_domain_model_stats(
    accumulator: dict[str, dict[str, dict[str, float]]],
    *,
    prior_strength: float = 4.0,
) -> dict[str, dict[str, dict[str, float]]]:
    global_valid = sum(stats["valid"] for models in accumulator.values() for stats in models.values() if models)
    global_calls = sum(stats["calls"] for models in accumulator.values() for stats in models.values() if models)
    global_rate = (global_valid / global_calls) if global_calls else 0.75
    finalized: dict[str, dict[str, dict[str, float]]] = {}
    for domain, models in accumulator.items():
        finalized[domain] = {}
        for model, stats in models.items():
            calls = stats["calls"]
            valid = stats["valid"]
            valid_rate = valid / calls if calls else global_rate
            finalized[domain][model] = {
                "calls": calls,
                "valid": valid,
                "valid_rate": valid_rate,
                "valid_rate_smoothed": ((valid + (prior_strength * global_rate)) / (calls + prior_strength))
                if calls
                else global_rate,
                "confidence": calls / (calls + prior_strength) if calls else 0.0,
                "avg_total_tokens": stats["tokens"] / calls if calls else 0.0,
                "avg_cost_usd": stats["cost"] / calls if calls else 0.0,
                "avg_latency_ms": stats["latency_ms"] / calls if calls else 0.0,
            }
    return finalized


def _empirical_stats_for(weights: MatrixRegressionWeights, domain: str, model: str, prompt: str = "") -> dict[str, float]:
    stats = weights.domain_model_stats or {}
    normalized_domain = _normalize_domain(domain)
    fallback = {
        "calls": 0.0,
        "valid": 0.0,
        "valid_rate": weights.target_mean,
        "valid_rate_smoothed": weights.target_mean,
        "confidence": 0.0,
        "avg_total_tokens": 0.0,
        "avg_cost_usd": 0.0,
        "avg_latency_ms": 0.0,
    }
    row = stats.get(_domain_shape_key(normalized_domain, prompt), {}).get(model)
    if row is None:
        row = stats.get(normalized_domain, {}).get(model)
    if row is None:
        row = stats.get("__overall__", {}).get(model)
    if row is None:
        return fallback
    return {
        "calls": float(row.get("calls") or 0.0),
        "valid": float(row.get("valid") or 0.0),
        "valid_rate": float(row.get("valid_rate") or 0.0),
        "valid_rate_smoothed": float(row.get("valid_rate_smoothed") or weights.target_mean),
        "confidence": float(row.get("confidence") or 0.0),
        "avg_total_tokens": float(row.get("avg_total_tokens") or 0.0),
        "avg_cost_usd": float(row.get("avg_cost_usd") or 0.0),
        "avg_latency_ms": float(row.get("avg_latency_ms") or 0.0),
    }


def _risk_adjusted_score(base_score: float, empirical_utility: float, empirical_confidence: float) -> float:
    confidence = _clamp(empirical_confidence, 0.0, 1.0)
    utility = _clamp(empirical_utility, 0.0, 1.0)
    reward = 0.08 * confidence * max(0.0, utility - 0.90)
    penalty = 0.18 * confidence * max(0.0, 0.92 - utility)
    return base_score + reward - penalty


def _wilson_lower(successes: int, observations: int) -> float:
    if observations <= 0 or not 0 <= successes <= observations:
        return 0.0
    rate = successes / observations
    z = 1.959963984540054
    denominator = 1.0 + z * z / observations
    center = rate + z * z / (2.0 * observations)
    margin = z * math.sqrt(
        rate * (1.0 - rate) / observations
        + z * z / (4.0 * observations * observations)
    )
    return max(0.0, (center - margin) / denominator)


def _predicted_total_tokens(estimated_total_tokens: int, empirical: dict[str, float]) -> float:
    observed = float(empirical.get("avg_total_tokens") or 0.0)
    confidence = _clamp(float(empirical.get("confidence") or 0.0), 0.0, 1.0)
    if observed <= 0.0 or confidence <= 0.0:
        return float(estimated_total_tokens)
    return max(1.0, ((1.0 - confidence) * float(estimated_total_tokens)) + (confidence * observed))


def _coerce_domain_model_stats(value: object) -> dict[str, dict[str, dict[str, float]]] | None:
    if not isinstance(value, dict):
        return None
    coerced: dict[str, dict[str, dict[str, float]]] = {}
    for domain, models in value.items():
        if not isinstance(models, dict):
            continue
        coerced[str(domain)] = {}
        for model, stats in models.items():
            if not isinstance(stats, dict):
                continue
            coerced[str(domain)][str(model)] = {
                str(key): float(number)
                for key, number in stats.items()
                if isinstance(number, int | float)
            }
    return coerced or None


def _ridge_regression(matrix: list[list[float]], targets: list[float], ridge_lambda: float) -> list[float]:
    width = len(matrix[0])
    xtx = [[0.0 for _ in range(width)] for _ in range(width)]
    xty = [0.0 for _ in range(width)]
    for row, target in zip(matrix, targets):
        for i in range(width):
            xty[i] += row[i] * target
            for j in range(width):
                xtx[i][j] += row[i] * row[j]
    for index in range(1, width):
        xtx[index][index] += ridge_lambda
    return _solve_linear_system(xtx, xty)


def _solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            augmented[pivot][column] = 1e-12
        if pivot != column:
            augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [value / scale for value in augmented[column]]
        for row_index in range(size):
            if row_index == column:
                continue
            factor = augmented[row_index][column]
            if factor == 0:
                continue
            augmented[row_index] = [
                value - (factor * pivot_value)
                for value, pivot_value in zip(augmented[row_index], augmented[column])
            ]
    return [augmented[row][-1] for row in range(size)]


def _bounds(values: Any) -> tuple[float, float]:
    materialized = list(values)
    if not materialized:
        return 0.0, 1.0
    minimum = min(materialized)
    maximum = max(materialized)
    if maximum <= minimum:
        return minimum, minimum + 1.0
    return minimum, maximum


def _inverse_range(value: float, minimum: float, maximum: float) -> float:
    if maximum <= minimum:
        return 1.0
    scaled = 1.0 - ((value - minimum) / (maximum - minimum))
    return max(0.10, min(1.0, 0.10 + (0.90 * scaled)))


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
