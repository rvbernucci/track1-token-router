#!/usr/bin/env python3
"""Fit a leakage-safe, runtime-cheap Kimi-vs-MiniMax challenger.

The script deliberately emits reports and a candidate artifact only. It never edits
the production policy. Candidate overrides must beat the production choice in
paired development data after Holm correction; the protected holdout is opened
only once for the final comparison.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
KIMI = "accounts/fireworks/models/kimi-k2p7-code"
MINIMAX = "accounts/fireworks/models/minimax-m3"
MODELS = (KIMI, MINIMAX)
DEFAULT_PAIRED_DIRS = (
    "reports/generated/fireworks-champion-v3",
    "reports/generated/s80-fireworks-4400-duel",
)
RAW_SCORE_FEATURES = (
    "fg.deterministic_fit",
    "fg.format_complexity",
    "fg.generation_demand",
    "fg.knowledge_uncertainty",
    "fg.reasoning_demand",
)
STRUCTURAL_FEATURES = (
    "mechanical.prompt_tokens_log",
    "mechanical.word_count_log",
    "mechanical.number_density",
    "mechanical.operator_count",
    "mechanical.code_lines_log",
    "prompt.constraint_count",
)


def rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def atomic_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(value, sort_keys=True) + "\n" for value in values), encoding="utf-8"
    )
    temporary.replace(path)


def exact_mcnemar(left_only: int, right_only: int) -> float:
    discordant = left_only + right_only
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, index) for index in range(min(left_only, right_only) + 1))
    return min(1.0, 2.0 * tail / (2**discordant))


def holm_adjust(candidates: list[dict[str, Any]]) -> None:
    ordered = sorted(candidates, key=lambda item: (item["p_raw"], item["rule_id"]))
    running = 0.0
    total = len(ordered)
    for index, candidate in enumerate(ordered):
        running = max(running, min(1.0, candidate["p_raw"] * (total - index)))
        candidate["p_holm"] = running


def other(model: str) -> str:
    return MINIMAX if model == KIMI else KIMI


def short_model(model: str) -> str:
    return "kimi" if model == KIMI else "minimax"


def ledger_role(row: dict[str, Any]) -> str:
    role = row.get("role")
    if role in {"fit", "calibration", "protected_holdout"}:
        return str(role)
    split = row.get("split")
    if split in {"train", "fit"}:
        return "fit"
    if split in {"validation", "calibration"}:
        return "calibration"
    return "protected_holdout"


def contract_class(features: dict[str, float]) -> str:
    for name in ("code", "json", "label", "list", "number", "free_text"):
        if features.get(f"contract.kind.{name}", 0.0) >= 0.5:
            return name
    for name in ("code", "json", "number", "short_text", "list", "boolean", "free_text"):
        if features.get(f"mechanical.shape.{name}", 0.0) >= 0.5:
            return name
    return "unknown"


def response_length_class(row: dict[str, Any]) -> str:
    features = row["features"]
    contract = contract_class(features)
    if contract in {"label", "number", "short_text", "boolean"}:
        return "short"
    if features.get("contract.max_words_log", 0.0) > 0:
        value = math.expm1(float(features["contract.max_words_log"]))
        return "short" if value <= 12 else "medium" if value <= 100 else "long"
    if row["category"] in {"summarization", "code_generation"}:
        return "long"
    if contract in {"code", "json", "list"} or row["category"] in {"code_debugging", "factual_qa"}:
        return "medium"
    return "short"


def feature_record(row: dict[str, Any]) -> dict[str, Any]:
    features = row["features"]
    record: dict[str, Any] = {
        "category": row["category"],
        "intent": row.get("intent", row["category"]),
        "difficulty": row.get("difficulty", "unspecified"),
        "contract": contract_class(features),
        "response_length": response_length_class(row),
        "strict_contract": int(features.get("contract.strict", 0.0) >= 0.5),
    }
    for name in RAW_SCORE_FEATURES + STRUCTURAL_FEATURES:
        record[name] = float(features.get(name, 0.0))
    return record


def load_policy(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "default_model": payload["default_model"],
        "intent_models": payload["intent_models"],
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def policy_model(policy: dict[str, Any], record: dict[str, Any]) -> str:
    return policy["intent_models"].get(record["intent"], policy["default_model"])


def load_observations(
    ledger_path: Path, paired_dirs: list[Path]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ledger = {row["task_id"]: row for row in rows(ledger_path)}
    verdicts: dict[tuple[str, str], dict[str, Any]] = {}
    responses: dict[tuple[str, str], dict[str, Any]] = {}
    audit: dict[str, Any] = {"sources": [], "ignored_duplicate_pairs": 0, "pending_unjudged_pairs": 0}

    for directory in paired_dirs:
        source_verdicts = rows(directory / "final-verdicts.jsonl")
        source_responses = rows(directory / "responses.jsonl")
        audit["sources"].append(
            {
                "directory": str(directory.relative_to(ROOT) if directory.is_relative_to(ROOT) else directory),
                "responses": len(source_responses),
                "verdicts": len(source_verdicts),
                "status": "usable" if source_verdicts else "pending_labels",
            }
        )
        if not source_verdicts:
            audit["pending_unjudged_pairs"] += len(source_responses)
            continue
        local_responses = {(row["task_id"], row["model"]): row for row in source_responses}
        for verdict in source_verdicts:
            key = (verdict["task_id"], verdict["model"])
            if verdict.get("correct") is None or key not in local_responses:
                continue
            if key in verdicts:
                audit["ignored_duplicate_pairs"] += 1
                continue
            verdicts[key] = verdict
            responses[key] = local_responses[key]

    task_ids = sorted({task_id for task_id, _ in verdicts})
    observations: list[dict[str, Any]] = []
    for task_id in task_ids:
        if task_id not in ledger or any((task_id, model) not in verdicts for model in MODELS):
            continue
        item = ledger[task_id]
        record = feature_record(item)
        outcome = {model: bool(verdicts[(task_id, model)]["correct"]) for model in MODELS}
        token_usage = {
            model: int((responses[(task_id, model)].get("usage") or {}).get("total", 0)) for model in MODELS
        }
        observations.append(
            {
                "task_id": task_id,
                "role": ledger_role(item),
                "features": record,
                "correct": outcome,
                "tokens": token_usage,
                "tie_correct": outcome[KIMI] == outcome[MINIMAX],
            }
        )
    audit["complete_tasks"] = len(observations)
    audit["role_counts"] = dict(Counter(row["role"] for row in observations))
    return observations, audit


def quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def candidate_predicates(development: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any], Callable[[dict[str, Any]], bool]]]:
    predicates: list[tuple[str, dict[str, Any], Callable[[dict[str, Any]], bool]]] = []
    categories = sorted({row["features"]["category"] for row in development})
    categorical = ("difficulty", "contract", "response_length", "strict_contract")
    for category in categories:
        predicates.append(
            (f"category={category}", {"category": category}, lambda r, c=category: r["category"] == c)
        )
        category_rows = [row for row in development if row["features"]["category"] == category]
        for name in categorical:
            for value in sorted({row["features"][name] for row in category_rows}, key=str):
                spec = {"category": category, name: value}
                predicates.append(
                    (
                        f"category={category}&{name}={value}",
                        spec,
                        lambda r, c=category, n=name, v=value: r["category"] == c and r[n] == v,
                    )
                )
        for name in RAW_SCORE_FEATURES + STRUCTURAL_FEATURES:
            values = [float(row["features"][name]) for row in category_rows]
            for q in (0.25, 0.5, 0.75):
                threshold = quantile(values, q)
                for operator in ("le", "gt"):
                    spec = {"category": category, "feature": name, "operator": operator, "threshold": threshold}
                    predicates.append(
                        (
                            f"category={category}&{name}{'<=' if operator == 'le' else '>'}{threshold:.6g}",
                            spec,
                            lambda r, c=category, n=name, op=operator, t=threshold: r["category"] == c
                            and (float(r[n]) <= t if op == "le" else float(r[n]) > t),
                        )
                    )
    unique: dict[str, tuple[str, dict[str, Any], Callable[[dict[str, Any]], bool]]] = {}
    for candidate in predicates:
        unique[candidate[0]] = candidate
    return list(unique.values())


def evaluate_policy(
    observations: list[dict[str, Any]],
    policy: dict[str, Any],
    rules: list[dict[str, Any]],
) -> dict[str, Any]:
    correct = 0
    tokens = 0
    selections = Counter()
    predictions: list[dict[str, Any]] = []
    for row in observations:
        record = row["features"]
        model = policy_model(policy, record)
        matched_rule = None
        for rule in rules:
            if matches(record, rule["predicate"]):
                model = rule["model"]
                matched_rule = rule["rule_id"]
                break
        is_correct = row["correct"][model]
        correct += int(is_correct)
        tokens += row["tokens"][model]
        selections[short_model(model)] += 1
        predictions.append(
            {
                "task_id": row["task_id"],
                "role": row["role"],
                "model": model,
                "correct": is_correct,
                "tokens": row["tokens"][model],
                "rule_id": matched_rule,
                "tie_correct": row["tie_correct"],
            }
        )
    return {
        "tasks": len(observations),
        "correct": correct,
        "accuracy": correct / len(observations) if observations else None,
        "tokens": tokens,
        "selections": dict(selections),
        "predictions": predictions,
    }


def matches(record: dict[str, Any], predicate: dict[str, Any]) -> bool:
    if record["category"] != predicate["category"]:
        return False
    if "feature" in predicate:
        value = float(record[predicate["feature"]])
        return value <= predicate["threshold"] if predicate["operator"] == "le" else value > predicate["threshold"]
    return all(record.get(name) == value for name, value in predicate.items())


def train_rules(
    development: list[dict[str, Any]], policy: dict[str, Any], alpha: float, min_cohort: int, min_discordant: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    for rule_id, predicate, matcher in candidate_predicates(development):
        cohort = [row for row in development if matcher(row["features"])]
        if len(cohort) < min_cohort:
            continue
        baseline_models = {policy_model(policy, row["features"]) for row in cohort}
        if len(baseline_models) != 1:
            continue
        baseline = next(iter(baseline_models))
        challenger = other(baseline)
        baseline_only = sum(row["correct"][baseline] and not row["correct"][challenger] for row in cohort)
        challenger_only = sum(row["correct"][challenger] and not row["correct"][baseline] for row in cohort)
        discordant = baseline_only + challenger_only
        if discordant < min_discordant:
            continue
        baseline_tokens = sum(row["tokens"][baseline] for row in cohort)
        challenger_tokens = sum(row["tokens"][challenger] for row in cohort)
        candidates.append(
            {
                "rule_id": rule_id,
                "predicate": predicate,
                "model": challenger,
                "cohort_size": len(cohort),
                "baseline_model": baseline,
                "baseline_only_correct": baseline_only,
                "challenger_only_correct": challenger_only,
                "discordant": discordant,
                "accuracy_gain": (challenger_only - baseline_only) / len(cohort),
                "token_delta": challenger_tokens - baseline_tokens,
                "p_raw": exact_mcnemar(baseline_only, challenger_only),
                "challenger_has_accuracy_advantage": challenger_only > baseline_only,
            }
        )
    holm_adjust(candidates)
    supported = [
        candidate
        for candidate in candidates
        if candidate["challenger_has_accuracy_advantage"] and candidate["p_holm"] <= alpha
    ]
    supported.sort(key=lambda item: (-item["accuracy_gain"], item["token_delta"], item["p_holm"], item["rule_id"]))

    # Greedily retain only rules that improve development accuracy, then tokens.
    selected: list[dict[str, Any]] = []
    current = evaluate_policy(development, policy, selected)
    for candidate in supported:
        proposal = selected + [candidate]
        result = evaluate_policy(development, policy, proposal)
        if (result["correct"], -result["tokens"]) > (current["correct"], -current["tokens"]):
            selected.append(candidate)
            current = result
    return selected, sorted(candidates, key=lambda item: (item["p_holm"], -item["accuracy_gain"], item["rule_id"]))


def strip_predictions(metrics: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metrics.items() if key != "predictions"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=Path("evals/router-ml-v3/ledger.jsonl"))
    parser.add_argument("--policy", type=Path, default=Path("configs/fireworks-intent-policy-v2.json"))
    parser.add_argument("--paired-dir", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=Path("reports/generated/s80-fireworks-pair-selector"))
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--min-cohort", type=int, default=20)
    parser.add_argument("--min-discordant", type=int, default=6)
    args = parser.parse_args()
    resolve = lambda path: path if path.is_absolute() else ROOT / path
    paired_dirs = [resolve(path) for path in args.paired_dir] or [ROOT / path for path in DEFAULT_PAIRED_DIRS]
    output = resolve(args.output_dir)
    policy = load_policy(resolve(args.policy))
    observations, audit = load_observations(resolve(args.ledger), paired_dirs)
    development = [row for row in observations if row["role"] in {"fit", "calibration"}]
    holdout = [row for row in observations if row["role"] == "protected_holdout"]
    if not development or not holdout:
        raise SystemExit("Both development and protected holdout observations are required")

    rules, candidates = train_rules(development, policy, args.alpha, args.min_cohort, args.min_discordant)
    baseline_dev = evaluate_policy(development, policy, [])
    challenger_dev = evaluate_policy(development, policy, rules)
    baseline_holdout = evaluate_policy(holdout, policy, [])
    challenger_holdout = evaluate_policy(holdout, policy, rules)
    dominates = (challenger_holdout["correct"], -challenger_holdout["tokens"]) > (
        baseline_holdout["correct"], -baseline_holdout["tokens"]
    )
    ties = Counter()
    for row in observations:
        if row["correct"][KIMI] and row["correct"][MINIMAX]:
            ties["both_correct"] += 1
        elif not row["correct"][KIMI] and not row["correct"][MINIMAX]:
            ties["both_incorrect"] += 1
        elif row["correct"][KIMI]:
            ties["kimi_only"] += 1
        else:
            ties["minimax_only"] += 1

    artifact = {
        "schema_version": "fireworks-pair-selector-s80-v1",
        "objective": "maximize_accuracy_then_minimize_tokens",
        "baseline": policy,
        "rules": rules,
        "feature_schema": {
            "categorical": ["category", "intent", "difficulty", "contract", "response_length", "strict_contract"],
            "functiongemma_raw_scores": list(RAW_SCORE_FEATURES),
            "mechanical": list(STRUCTURAL_FEATURES),
        },
        "runtime": {
            "dependencies": "Python standard library only",
            "evaluation": "ordered predicate list over precomputed assessment/mechanical features",
            "asymptotic_cost": f"O({max(1, len(rules))}) predicates per task",
        },
    }
    atomic_json(output / "candidate-artifact.json", artifact)
    artifact_sha = hashlib.sha256((output / "candidate-artifact.json").read_bytes()).hexdigest()
    summary = {
        "schema_version": "fireworks-pair-selector-s80-report-v1",
        "decision": "promote" if dominates else "do_not_promote",
        "dominates_intent_policy_v2": dominates,
        "artifact_sha256": artifact_sha,
        "audit": audit,
        "outcomes": dict(ties),
        "candidate_cohorts_tested": len(candidates),
        "statistically_supported_rules": len(rules),
        "baseline_development": strip_predictions(baseline_dev),
        "challenger_development": strip_predictions(challenger_dev),
        "baseline_protected_holdout": strip_predictions(baseline_holdout),
        "challenger_protected_holdout": strip_predictions(challenger_holdout),
        "holdout_accuracy_delta": challenger_holdout["accuracy"] - baseline_holdout["accuracy"],
        "holdout_token_delta": challenger_holdout["tokens"] - baseline_holdout["tokens"],
        "selection_protocol": {
            "training_roles": ["fit", "calibration"],
            "protected_role": "protected_holdout",
            "paired_test": "exact McNemar",
            "multiple_testing": "Holm family-wise correction",
            "alpha": args.alpha,
            "min_cohort": args.min_cohort,
            "min_discordant": args.min_discordant,
            "ties": "Either model is accuracy-correct; tokens break aggregate policy ties.",
        },
    }
    atomic_json(output / "summary.json", summary)
    atomic_json(output / "cohort-audit.json", candidates)
    atomic_jsonl(output / "protected-holdout-predictions.jsonl", challenger_holdout["predictions"])

    baseline_h = summary["baseline_protected_holdout"]
    challenger_h = summary["challenger_protected_holdout"]
    source_lines = "\n".join(
        f"- `{source['directory']}`: {source['status']} ({source['responses']} responses, {source['verdicts']} verdicts)"
        for source in audit["sources"]
    )
    rule_lines = "\n".join(
        f"- `{rule['rule_id']}` -> `{short_model(rule['model'])}` "
        f"(Holm p={rule['p_holm']:.6g}, development gain={rule['accuracy_gain']:.2%})"
        for rule in rules
    ) or "- No override survived the leakage-safe statistical gates."
    readme = f"""# Sprint 80 Fireworks Pair Selector

## Decision

**{summary['decision'].replace('_', ' ').title()}.** The challenger {'dominates' if dominates else 'does not dominate'} `intent-policy-v2` on the protected holdout.

| Policy | Correct | Accuracy | Tokens |
|---|---:|---:|---:|
| intent-policy-v2 | {baseline_h['correct']}/{baseline_h['tasks']} | {baseline_h['accuracy']:.2%} | {baseline_h['tokens']:,} |
| learned challenger | {challenger_h['correct']}/{challenger_h['tasks']} | {challenger_h['accuracy']:.2%} | {challenger_h['tokens']:,} |

Holdout delta: **{summary['holdout_accuracy_delta']:+.2%} accuracy**, **{summary['holdout_token_delta']:+,} tokens**.

## Protocol

- Inputs: raw FunctionGemma intent and five scores, prompt/mechanical features, expected contract, and expected response-length class.
- Fit boundary: only `fit` and `calibration`; `protected_holdout` is used once for the final report.
- Labels explicitly preserve `both_correct`, `both_incorrect`, `kimi_only`, and `minimax_only`; either model wins an accuracy tie.
- Overrides require an exact paired McNemar advantage after Holm family-wise correction.
- Objective is lexicographic: accuracy first, tokens second.

## Supported Rules

{rule_lines}

## Data Sources

{source_lines}

The S80 4,400 duel is automatically ingested once a sibling `final-verdicts.jsonl` exists. Responses without verdicts are reported as pending and never treated as labels.

## Minimal Runtime Evaluator

The candidate artifact is `{(output / 'candidate-artifact.json').name}` (SHA-256 `{artifact_sha}`). A production evaluator would deserialize it once, reuse already-computed FunctionGemma/mechanical features, apply the ordered predicates, and intersect the selected model with `ALLOWED_MODELS`. It needs no ML framework and no additional model inference.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
