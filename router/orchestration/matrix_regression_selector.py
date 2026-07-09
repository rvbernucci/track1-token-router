from __future__ import annotations

import json
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
    "capability",
    "correlation",
    "reliability",
    "cost_utility",
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
    cost_bounds = _bounds(float(row.get("estimated_cost_usd") or 0.0) for row in rows)
    latency_bounds = _bounds(float(row.get("latency_ms") or 0.0) for row in rows)
    matrix: list[list[float]] = []
    targets: list[float] = []
    observed_models: set[str] = set()
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
        matrix.append(_feature_vector(candidate, tier, domain, reasoning_effort))
        targets.append(_target(row, cost_bounds, latency_bounds))
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
    scored = []
    for candidate in pool:
        reasoning_effort = select_reasoning_effort(candidate.model, task_profile.tier)
        features = _feature_vector(candidate, task_profile.tier, task_profile.domain, reasoning_effort)
        regression_score = weights.predict(features)
        regression_utility = _clamp(regression_score, 0.0, 1.0)
        score_weights = _hybrid_score_weights(task_profile.tier)
        hybrid_score = (
            (score_weights["regression"] * regression_utility)
            + (score_weights["nash"] * candidate.nash_product)
            + (score_weights["cost"] * candidate.cost_utility)
        )
        scored.append(
            {
                "model": candidate.model,
                "regression_score": regression_score,
                "regression_utility": regression_utility,
                "hybrid_score": hybrid_score,
                "hybrid_score_weights": score_weights,
                "nash_product": candidate.nash_product,
                "estimated_cost_usd": candidate.estimated_cost_usd,
                "features": dict(zip(FEATURE_NAMES, features)),
            }
        )
    selected = max(scored, key=lambda row: (row["hybrid_score"], -row["estimated_cost_usd"], row["model"]))
    return {
        "model": selected["model"],
        "selection_rule": "matrix_regression_plus_nash",
        "tier": task_profile.tier,
        "domain": task_profile.domain,
        "observed_model_filter": weights.observed_models,
        "ranked_candidates": sorted(
            scored,
            key=lambda row: (row["hybrid_score"], -row["estimated_cost_usd"], row["model"]),
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


def _feature_vector(candidate: Any, tier: str, domain: str, reasoning_effort: str | None) -> list[float]:
    family = _model_family(candidate.model)
    reasoning = reasoning_effort or "omitted"
    domain = _normalize_domain(domain)
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
        min(candidate.capability / 4.0, 1.0),
        candidate.correlation,
        candidate.reliability,
        candidate.cost_utility,
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


def _hybrid_score_weights(tier: str) -> dict[str, float]:
    if tier == "strong":
        return {"regression": 0.85, "nash": 0.10, "cost": 0.05}
    if tier == "medium":
        return {"regression": 0.70, "nash": 0.20, "cost": 0.10}
    return {"regression": 0.55, "nash": 0.25, "cost": 0.20}


def _target(row: dict[str, Any], cost_bounds: tuple[float, float], latency_bounds: tuple[float, float]) -> float:
    valid = bool(row.get("valid"))
    cost_utility = _inverse_range(float(row.get("estimated_cost_usd") or 0.0), *cost_bounds)
    latency_utility = _inverse_range(float(row.get("latency_ms") or 0.0), *latency_bounds)
    return (0.80 if valid else 0.0) + (0.15 * cost_utility) + (0.05 * latency_utility)


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
