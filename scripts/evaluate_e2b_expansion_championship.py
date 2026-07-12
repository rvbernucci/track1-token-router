#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCORES = (
    "deterministic_fit", "reasoning_demand", "knowledge_uncertainty",
    "generation_demand", "format_complexity",
)
CATEGORIES = (
    "factual_qa", "math_reasoning", "sentiment", "summarization", "ner",
    "code_debugging", "logic_puzzle", "code_generation",
)


def main() -> int:
    rows = _jsonl(ROOT / "reports/generated/e2b-expansion-v1/regression-ledger.jsonl")
    candidate = json.loads((ROOT / "configs/e2b-category-matrix-regression-v2.json").read_text())
    current = json.loads((ROOT / "configs/e2b-270m-matrix-regression.json").read_text())
    eligible = [row for row in rows if row.get("assessment_valid")]
    reports = {
        "current_sentiment_only": _evaluate(eligible, current),
        "category_candidate": _evaluate(eligible, candidate),
    }
    counterexamples = [
        {"task_id": row["task_id"], "category": row["category"], "source": row["source"], "role": row["role"]}
        for row in eligible if _selected(row, candidate)[0] and not int(row["target"])
    ]
    generated = ROOT / "reports/generated/e2b-expansion-v1"
    generated.mkdir(parents=True, exist_ok=True)
    (generated / "category-counterexamples.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in counterexamples), encoding="utf-8",
    )
    payload = {
        "schema_version": "e2b-expansion-championship-v1",
        "rows": len(eligible),
        "policies": reports,
        "candidate_default_enabled": bool(candidate.get("default_enabled")),
        "counterexamples": len(counterexamples),
        "interpretation": "Remote fallback correctness is not assumed; reported accuracy is precision among released E2B answers.",
    }
    (generated / "championship-scorecard.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    public = ROOT / "reports/public/e2b-expansion-championship-scorecard.md"
    public.write_text(_markdown(payload), encoding="utf-8")
    print(json.dumps({"rows": len(eligible), "candidate": reports["category_candidate"]["overall"]}, sort_keys=True))
    return 0


def _evaluate(rows: Sequence[Mapping[str, Any]], policy: Mapping[str, Any]) -> dict[str, Any]:
    selected = [row for row in rows if _selected(row, policy)[0]]
    protected = [row for row in rows if row["role"] in {"protected_holdout", "external_audit"}]
    selected_protected = [row for row in selected if row["role"] in {"protected_holdout", "external_audit"}]
    report = {
        "overall": _metrics(rows, selected),
        "protected_evidence": _metrics(protected, selected_protected),
        "by_role": {},
        "by_category": {},
    }
    for role in sorted({str(row["role"]) for row in rows}):
        population = [row for row in rows if row["role"] == role]
        cohort = [row for row in selected if row["role"] == role]
        report["by_role"][role] = _metrics(population, cohort)
    for category in CATEGORIES:
        population = [row for row in rows if row["category"] == category]
        cohort = [row for row in selected if row["category"] == category]
        report["by_category"][category] = _metrics(population, cohort)
    scenarios = {}
    for focus in ("uniform", "factual_qa", "summarization", "code_generation", "logic_puzzle"):
        weights = {category: (1.0 if focus == "uniform" else (4.0 if category == focus else 1.0)) for category in CATEGORIES}
        scenarios[focus] = _weighted_metrics(rows, selected, weights)
    report["scenarios"] = scenarios
    return report


def _metrics(population: Sequence[Mapping[str, Any]], selected: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    correct = sum(int(row["target"]) for row in selected)
    estimated_tokens = sum(_estimated_prompt_tokens(row) for row in selected)
    return {
        "population": len(population), "selected": len(selected), "correct": correct,
        "precision": correct / len(selected) if selected else 0.0,
        "coverage": len(selected) / len(population) if population else 0.0,
        "fireworks_calls_avoided": len(selected),
        "estimated_fireworks_input_tokens_avoided": estimated_tokens,
    }


def _weighted_metrics(
    population: Sequence[Mapping[str, Any]], selected: Sequence[Mapping[str, Any]], weights: Mapping[str, float],
) -> dict[str, float]:
    population_mass = sum(weights[str(row["category"])] for row in population)
    selected_mass = sum(weights[str(row["category"])] for row in selected)
    correct_mass = sum(weights[str(row["category"])] * int(row["target"]) for row in selected)
    return {
        "coverage": selected_mass / population_mass if population_mass else 0.0,
        "precision": correct_mass / selected_mass if selected_mass else 0.0,
    }


def _selected(row: Mapping[str, Any], policy: Mapping[str, Any]) -> tuple[bool, float]:
    intent = str(row["predicted_intent"])
    if intent not in set(policy.get("allowed_intents", [])):
        return False, 0.0
    coefficients = policy["models_by_intent"][intent]
    values = [float(row["scores"][name]) / 10.0 for name in SCORES]
    mechanical_names = policy.get("mechanical_feature_names", [])
    values.extend(float(row["mechanical_features"][name]) for name in mechanical_names)
    normalization = policy.get("normalization_by_intent", {}).get(intent)
    if normalization:
        values = [
            (value - float(mean)) / float(scale)
            for value, mean, scale in zip(values, normalization["mean"], normalization["scale"], strict=True)
        ]
    probability = _sigmoid(float(coefficients[0]) + sum(
        float(weight) * value for weight, value in zip(coefficients[1:], values, strict=True)
    ))
    calibrator = policy.get("calibrators_by_intent", {}).get(intent)
    if calibrator:
        bounded = min(1 - 1e-6, max(1e-6, probability))
        probability = _sigmoid(float(calibrator[0]) + float(calibrator[1]) * math.log(bounded / (1 - bounded)))
    threshold = float(policy.get("thresholds_by_intent", {}).get(intent, policy["decision_threshold"]))
    return probability >= threshold, probability


def _estimated_prompt_tokens(row: Mapping[str, Any]) -> int:
    value = float(row["mechanical_features"]["mechanical.prompt_tokens_log"])
    return max(1, round(math.exp(value * math.log1p(8192)) - 1))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, value))))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _markdown(payload: Mapping[str, Any]) -> str:
    lines = ["# E2B Expansion Championship Scorecard", ""]
    for name, report in payload["policies"].items():
        overall = report["overall"]
        protected = report["protected_evidence"]
        lines.extend([
            f"## {name.replace('_', ' ').title()}", "",
            f"- Selective local precision: `{overall['precision']:.2%}`",
            f"- Zero-Fireworks-token coverage: `{overall['coverage']:.2%}`",
            f"- Fireworks calls avoided in replay: `{overall['fireworks_calls_avoided']}`",
            f"- Estimated Fireworks input tokens avoided: `{overall['estimated_fireworks_input_tokens_avoided']}`", "",
            f"- Protected-evidence precision: `{protected['precision']:.2%}`",
            f"- Protected-evidence coverage: `{protected['coverage']:.2%}`", "",
        ])
    lines.extend([
        "Remote fallback correctness is deliberately not inferred from this E2B ledger. "
        "Accuracy above means precision among answers the local E2B route would release.", "",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
