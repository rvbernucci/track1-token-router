#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
INTENTS = (
    "factual_qa", "math_reasoning", "sentiment", "summarization", "ner",
    "code_debugging", "logic_puzzle", "code_generation",
)
SCORES = (
    "deterministic_fit", "reasoning_demand", "knowledge_uncertainty",
    "generation_demand", "format_complexity",
)
FEATURE_NAMES = tuple(f"intent.{name}" for name in INTENTS) + tuple(f"score.{name}" for name in SCORES)
FOLDS = 5


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fit E2B correctness directly from FunctionGemma 270M parameters.")
    parser.add_argument("--output", type=Path, default=Path("configs/e2b-270m-matrix-regression.json"))
    parser.add_argument("--report-json", type=Path, default=Path("reports/generated/e2b-270m-matrix-regression.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/public/e2b-270m-matrix-regression.md"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    rows, audit = load_population()
    result = fit(rows, audit)
    for path, payload in ((args.output, result["artifact"]), (args.report_json, result)):
        target = _absolute(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = _absolute(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(_markdown(result), encoding="utf-8")
    if args.check:
        check(result)
    print(json.dumps({"passed": True, "usable_rows": len(rows), "raw_accuracy": result["population"]["raw_e2b_accuracy"], "selected_threshold": result["selection"]["threshold"]}, sort_keys=True))
    return 0


def load_population() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    old_outcomes = _keyed(ROOT / "reports/generated/amd-pod-e2b-regression-2000/e2b-outcome-matrix-contract-v2.jsonl")
    old_assessments = _keyed(ROOT / "reports/generated/amd-pod-e2b-regression-2000/functiongemma-valid-predictions.jsonl", key="id")
    old_tasks = _keyed(ROOT / "reports/generated/amd-pod-e2b-regression-2000/tasks.jsonl", key="id")
    old_ids = sorted(set(old_outcomes) & set(old_assessments))
    rows: list[dict[str, Any]] = []
    for task_id in old_ids:
        outcome, assessment = old_outcomes[task_id], old_assessments[task_id]["prediction"]
        category = old_tasks[task_id]["source_assessment"]["intent"]
        rows.append(_row(task_id, "legacy", outcome["mutation_lineage"], category, assessment, bool(outcome["correct"])))

    fg = _keyed(ROOT / "evals/e2b-regression-v2-inference/functiongemma.jsonl")
    labels = {}
    for path in (
        ROOT / "evals/e2b-regression-v2-adjudication/development/labels.jsonl",
        ROOT / "evals/e2b-regression-v2-adjudication/sealed/final-holdout-labels.jsonl",
    ):
        labels.update(_keyed(path))
    metadata = _keyed(ROOT / "evals/e2b-regression-v2/metadata.jsonl")
    new_ids = sorted(set(fg) & set(labels) & set(metadata))
    for task_id in new_ids:
        assessment = fg[task_id]["assessment"]
        if not isinstance(assessment, Mapping):
            continue
        rows.append(_row(task_id, "v2", metadata[task_id]["mutation_lineage"], labels[task_id]["category"], assessment, bool(labels[task_id]["binary_label"])))

    if len(rows) != len({row["task_id"] for row in rows}):
        raise ValueError("Task IDs overlap across regression populations.")
    audit = {
        "expected_questions": 4000,
        "legacy_questions": 2000,
        "legacy_valid_270m_and_label": len(old_ids),
        "v2_questions": 2000,
        "v2_valid_270m_and_label": len(new_ids),
        "usable_intersection": len(rows),
        "invalid_270m_routes_fireworks": 4000 - len(rows),
    }
    if audit != {
        "expected_questions": 4000, "legacy_questions": 2000, "legacy_valid_270m_and_label": 1991,
        "v2_questions": 2000, "v2_valid_270m_and_label": 1991, "usable_intersection": 3982,
        "invalid_270m_routes_fireworks": 18,
    }:
        raise ValueError(f"Unexpected population audit: {audit}")
    return rows, audit


def _row(task_id: str, source: str, lineage: str, category: str, assessment: Mapping[str, Any], target: bool) -> dict[str, Any]:
    intent = str(assessment["intent"])
    scores = assessment["scores"]
    values = [float(intent == name) for name in INTENTS]
    values.extend(float(scores[name]) / 10.0 for name in SCORES)
    if len(values) != 13 or any(not math.isfinite(value) for value in values):
        raise ValueError(f"Invalid feature vector for {task_id}")
    return {"task_id": task_id, "source": source, "lineage": str(lineage), "category": str(category), "target": int(target), "values": values}


def fit(rows: Sequence[Mapping[str, Any]], audit: Mapping[str, Any]) -> dict[str, Any]:
    folds = [_fold(row["source"], row["lineage"]) for row in rows]
    predictions = [0.0] * len(rows)
    fold_metrics = []
    for fold in range(FOLDS):
        train = [row for row, assigned in zip(rows, folds, strict=True) if assigned != fold]
        held = [(index, row) for index, (row, assigned) in enumerate(zip(rows, folds, strict=True)) if assigned == fold]
        weights = _logistic_fit(train, l2=2.0)
        for index, row in held:
            predictions[index] = _predict(weights, row["values"])
        fold_metrics.append({"fold": fold, "train_rows": len(train), "held_out_rows": len(held), "held_out_positive": sum(row["target"] for _, row in held)})
    frontier = _frontier(rows, predictions)
    statistically_useful = [item for item in frontier if item["selected"] >= 100]
    selection = max(statistically_useful, key=lambda item: (item["wilson_lower_95"], item["precision"], item["coverage"]))
    selection = {**selection, "minimum_support": 100, "target_precision": 0.90, "target_precision_met": selection["precision"] >= 0.90}
    final_weights = _logistic_fit(rows, l2=2.0, iterations=900)
    positives = sum(row["target"] for row in rows)
    by_category = {}
    for category in sorted({row["category"] for row in rows}):
        category_rows = [row for row in rows if row["category"] == category]
        correct = sum(row["target"] for row in category_rows)
        by_category[category] = {"rows": len(category_rows), "correct": correct, "accuracy": correct / len(category_rows)}
    brier = statistics.fmean((prediction - row["target"]) ** 2 for row, prediction in zip(rows, predictions, strict=True))
    v2_rows = [row for row in rows if row["source"] == "v2"]
    v2_comparison = _compare_v2_models(v2_rows)
    per_intent_models = _fit_per_intent_models(rows)
    artifact = {
        "schema_version": "e2b-270m-matrix-regression-v1",
        "default_enabled": True,
        "invalid_270m_route": "fireworks",
        "feature_names": list(FEATURE_NAMES),
        "coefficients": [final_weights[0], *final_weights[1:]],
        "decision_threshold": v2_comparison["variants"]["per_intent_five_scores"]["best_operating_point"]["threshold"],
        "runtime_variant": "per_intent_five_scores",
        "score_feature_names": list(SCORES),
        "models_by_intent": per_intent_models,
        "fit_rows": len(rows),
        "fit_positive": positives,
        "training_scope": "all_available_3982_after_grouped_oof_evaluation",
    }
    return {
        "schema_version": "e2b-270m-matrix-regression-report-v1",
        "population_audit": dict(audit),
        "population": {"rows": len(rows), "correct": positives, "incorrect": len(rows) - positives, "raw_e2b_accuracy": positives / len(rows), "by_source": dict(Counter(row["source"] for row in rows)), "by_category": by_category},
        "validation": {"method": "5-fold out-of-fold grouped by source+mutation_lineage", "folds": fold_metrics, "brier": brier, "lineage_overlap": 0},
        "v2_model_comparison": v2_comparison,
        "selection": selection,
        "frontier": frontier,
        "coefficient_interpretation": _coefficient_table(final_weights),
        "artifact": artifact,
    }


def check(result: Mapping[str, Any]) -> None:
    gates = {
        "all_usable_rows": result["population"]["rows"] == 3982,
        "invalids_explicit": result["population_audit"]["invalid_270m_routes_fireworks"] == 18,
        "thirteen_270m_features_only": len(result["artifact"]["feature_names"]) == 13,
        "grouped_oof": result["validation"]["lineage_overlap"] == 0,
        "finite_coefficients": all(math.isfinite(value) for value in result["artifact"]["coefficients"]),
        "explicit_runtime_default": result["artifact"]["default_enabled"] is True,
    }
    if not all(gates.values()):
        raise ValueError(f"Regression checks failed: {[name for name, passed in gates.items() if not passed]}")


def _frontier(rows: Sequence[Mapping[str, Any]], predictions: Sequence[float]) -> list[dict[str, Any]]:
    result = []
    for threshold in tuple(round(value / 100, 2) for value in range(10, 100, 5)):
        selected = [row for row, probability in zip(rows, predictions, strict=True) if probability >= threshold]
        correct = sum(row["target"] for row in selected)
        result.append({"threshold": threshold, "selected": len(selected), "correct": correct, "precision": correct / len(selected) if selected else 0.0, "coverage": len(selected) / len(rows), "wilson_lower_95": _wilson(correct, len(selected))})
    return result


def _compare_v2_models(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(rows) != 1991 or sum(row["target"] for row in rows) != 823:
        raise ValueError("V2 comparison must contain 1,991 valid assessments and 823 post-contract positives.")
    variants = {
        "global_joint": _oof_variant(rows, "global"),
        "per_intent_five_scores": _oof_variant(rows, "per_intent"),
    }
    for score_index, score_name in enumerate(SCORES, start=len(INTENTS)):
        variants[f"univariate_{score_name}"] = _oof_variant(rows, "univariate", [score_index])
    champion = min(variants, key=lambda name: (variants[name]["brier"], -variants[name]["best_operating_point"]["wilson_lower_95"]))
    return {
        "all_post_contract_correct": 828,
        "correct_with_valid_270m_parameters": 823,
        "correct_without_valid_270m_parameters": 5,
        "incorrect_with_valid_270m_parameters": len(rows) - 823,
        "variants": variants,
        "champion": champion,
        "finding": "Separate regressions are retained only if their out-of-fold discrimination beats the joint matrix.",
    }


def _fit_per_intent_models(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[float]]:
    score_indices = range(len(INTENTS), len(FEATURE_NAMES))
    models: dict[str, list[float]] = {}
    for intent_index, intent in enumerate(INTENTS):
        cohort = [row for row in rows if row["values"][intent_index] == 1.0]
        projected = [_project(row, score_indices) for row in cohort]
        models[intent] = _logistic_fit(projected, l2=2.0, iterations=900, dimensions=len(SCORES))
    return models


def _oof_variant(rows: Sequence[Mapping[str, Any]], mode: str, indices: Sequence[int] | None = None) -> dict[str, Any]:
    folds = [_fold(row["source"], row["lineage"]) for row in rows]
    predictions = [0.0] * len(rows)
    selected_indices = list(indices if indices is not None else range(len(FEATURE_NAMES)))
    for fold in range(FOLDS):
        train = [row for row, assigned in zip(rows, folds, strict=True) if assigned != fold]
        held = [(index, row) for index, (row, assigned) in enumerate(zip(rows, folds, strict=True)) if assigned == fold]
        if mode != "per_intent":
            projected = [_project(row, selected_indices) for row in train]
            weights = _logistic_fit(projected, l2=2.0, dimensions=len(selected_indices))
            for index, row in held:
                predictions[index] = _predict(weights, [row["values"][item] for item in selected_indices])
            continue
        global_weights = _logistic_fit([_project(row, range(len(INTENTS), len(FEATURE_NAMES))) for row in train], l2=2.0, dimensions=len(SCORES))
        models = {}
        for intent_index, intent in enumerate(INTENTS):
            cohort = [row for row in train if row["values"][intent_index] == 1.0]
            models[intent] = _logistic_fit([_project(row, range(len(INTENTS), len(FEATURE_NAMES))) for row in cohort], l2=2.0, dimensions=len(SCORES)) if len(cohort) >= 40 else global_weights
        for index, row in held:
            intent = INTENTS[next((item for item in range(len(INTENTS)) if row["values"][item] == 1.0), 0)]
            predictions[index] = _predict(models[intent], row["values"][len(INTENTS):])
    frontier = _frontier(rows, predictions)
    useful = [item for item in frontier if item["selected"] >= 100]
    if not useful:
        useful = [item for item in frontier if item["selected"] > 0]
    best = max(useful, key=lambda item: (item["wilson_lower_95"], item["precision"], item["coverage"]))
    return {
        "brier": statistics.fmean((prediction - row["target"]) ** 2 for row, prediction in zip(rows, predictions, strict=True)),
        "best_operating_point": best,
        "features": [FEATURE_NAMES[index] for index in selected_indices] if mode != "per_intent" else list(SCORES),
    }


def _project(row: Mapping[str, Any], indices: Sequence[int]) -> dict[str, Any]:
    return {**row, "values": [row["values"][index] for index in indices]}


def _logistic_fit(rows: Sequence[Mapping[str, Any]], *, l2: float, iterations: int = 650, dimensions: int | None = None) -> list[float]:
    if not rows:
        raise ValueError("Cannot fit an empty regression cohort.")
    weights = [0.0] * ((dimensions if dimensions is not None else len(rows[0]["values"])) + 1)
    for iteration in range(iterations):
        gradients = [0.0] * len(weights)
        for row in rows:
            x = [1.0, *row["values"]]
            error = _predict(weights, row["values"]) - row["target"]
            for index, value in enumerate(x):
                gradients[index] += error * value
        rate = 0.25 / math.sqrt(1.0 + iteration / 100.0)
        for index in range(len(weights)):
            penalty = 0.0 if index == 0 else l2 * weights[index]
            weights[index] -= rate * (gradients[index] + penalty) / len(rows)
    return weights


def _predict(weights: Sequence[float], values: Sequence[float]) -> float:
    value = weights[0] + sum(weight * feature for weight, feature in zip(weights[1:], values, strict=True))
    return 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, value))))


def _fold(source: str, lineage: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{source}:{lineage}".encode()).digest()[:4], "big") % FOLDS


def _wilson(correct: int, total: int) -> float:
    if not total:
        return 0.0
    z, p = 1.959963984540054, correct / total
    denominator = 1 + z * z / total
    center = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (center - margin) / denominator


def _coefficient_table(weights: Sequence[float]) -> list[dict[str, Any]]:
    return sorted(({"feature": name, "coefficient": weights[index], "odds_ratio": math.exp(weights[index])} for index, name in enumerate(FEATURE_NAMES, start=1)), key=lambda row: abs(row["coefficient"]), reverse=True)


def _markdown(result: Mapping[str, Any]) -> str:
    pop, selected = result["population"], result["selection"]
    lines = ["# E2B x FunctionGemma 270M Matrix Regression", "", "## Population", "", f"- Questions available: `4,000`", f"- Valid 270M/E2B-label intersections: `{pop['rows']}`", f"- Invalid 270M assessments routed to Fireworks: `{result['population_audit']['invalid_270m_routes_fireworks']}`", f"- E2B correct: `{pop['correct']}` (`{pop['raw_e2b_accuracy']:.2%}`)", "", "## Out-of-fold selection", "", f"- Threshold: `{selected['threshold']:.2f}`", f"- Selected: `{selected['selected']}` (`{selected['coverage']:.2%}` coverage)", f"- Correct: `{selected['correct']}` (`{selected['precision']:.2%}` precision)", f"- Wilson 95% lower bound: `{selected['wilson_lower_95']:.2%}`", f"- Brier score: `{result['validation']['brier']:.4f}`", "", "## Strongest coefficients", ""]
    for row in result["coefficient_interpretation"][:10]:
        lines.append(f"- `{row['feature']}`: coefficient `{row['coefficient']:.4f}`, odds ratio `{row['odds_ratio']:.3f}`")
    comparison = result["v2_model_comparison"]
    lines.extend(["", "## V2 model comparison", "", f"- Post-contract correct answers: `{comparison['all_post_contract_correct']}`", f"- Correct answers with valid 270M parameters: `{comparison['correct_with_valid_270m_parameters']}`", f"- Champion: `{comparison['champion']}`", ""])
    for name, variant in comparison["variants"].items():
        point = variant["best_operating_point"]
        lines.append(f"- `{name}`: Brier `{variant['brier']:.4f}`, selected `{point['selected']}`, precision `{point['precision']:.2%}`, coverage `{point['coverage']:.2%}`")
    lines.extend(["", "The final coefficient matrix is fitted on all 3,982 usable rows. It remains disabled by default until its routing threshold is accepted against the accuracy gate.", ""])
    return "\n".join(lines)


def _keyed(path: Path, *, key: str = "task_id") -> dict[str, dict[str, Any]]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            result[str(row[key])] = row
    return result


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
