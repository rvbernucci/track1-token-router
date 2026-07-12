#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
import argparse
import bisect
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any, Mapping, Sequence

try:
    import numpy as np
except ImportError:  # The submitted runtime does not need the research dependency.
    np = None


ROOT = Path(__file__).resolve().parents[1]
SCORES = (
    "deterministic_fit", "reasoning_demand", "knowledge_uncertainty",
    "generation_demand", "format_complexity",
)
INTENTS = (
    "factual_qa", "math_reasoning", "sentiment", "summarization", "ner",
    "code_debugging", "logic_puzzle", "code_generation",
)
FOLDS = 5


def main() -> int:
    parser = argparse.ArgumentParser(description="Fit or promote the Sprint 70 per-category E2B matrix.")
    parser.add_argument("--promote", action="store_true", help="Evaluate the frozen candidate on expansion holdout rows.")
    args = parser.parse_args()
    ledger_path = ROOT / "reports/generated/e2b-expansion-v1/regression-ledger.jsonl"
    rows = _jsonl(ledger_path)
    if not rows:
        raise ValueError("Category regression ledger is empty.")
    mechanical_names = tuple(sorted(rows[0]["mechanical_features"]))
    result = fit(rows, mechanical_names)
    freeze_path = ROOT / "evals/e2b-expansion-v1/frozen-candidate.json"
    candidate_digest = _artifact_sha256(result["artifact"])
    decision_digest = _decision_surface_sha256(result["artifact"])
    if args.promote:
        frozen = json.loads(freeze_path.read_text(encoding="utf-8"))
        if frozen.get("decision_surface_sha256") != decision_digest:
            raise ValueError("Frozen candidate hash changed after holdout freeze.")
        result = promote(result, rows, mechanical_names)
        result["frozen_candidate_sha256"] = frozen["artifact_sha256"]
        result["frozen_decision_surface_sha256"] = decision_digest
    else:
        freeze_path.write_text(json.dumps({
            "schema_version": "e2b-category-candidate-freeze-v1",
            "artifact_sha256": candidate_digest,
            "decision_surface_sha256": decision_digest,
            "allowed_intents": result["artifact"]["allowed_intents"],
            "thresholds_by_intent": result["artifact"]["thresholds_by_intent"],
            "fit_rows": result["population"]["fit"],
            "calibration_rows": result["population"]["calibration"],
            "holdout_opened": False,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result["frozen_candidate_sha256"] = candidate_digest
    config_path = ROOT / "configs/e2b-category-matrix-regression-v2.json"
    report_path = ROOT / "reports/generated/e2b-expansion-v1/category-calibration-candidate.json"
    public_path = ROOT / "reports/public/e2b-category-calibration-v2.md"
    public_json_path = ROOT / "reports/public/e2b-category-calibration-v2.json"
    for path, payload in ((config_path, result["artifact"]), (report_path, result)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    public_path.write_text(_markdown(result), encoding="utf-8")
    public_json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "passed": True, "rows": len(rows), "enabled_intents": result["artifact"]["allowed_intents"],
        "default_enabled": result["artifact"]["default_enabled"],
    }, sort_keys=True))
    return 0


def promote(result: dict[str, Any], rows: Sequence[Mapping[str, Any]], mechanical_names: Sequence[str]) -> dict[str, Any]:
    holdout = [
        row for row in rows
        if row["source"] == "expansion" and row["role"] == "protected_holdout" and row["assessment_valid"]
    ]
    if len(holdout) < 470:
        raise ValueError("Promotion requires the complete sealed expansion holdout.")
    artifact = result["artifact"]
    passed_intents = []
    metrics = {}
    for intent in artifact["allowed_intents"]:
        cohort = [row for row in holdout if row["predicted_intent"] == intent]
        selected = []
        for row in cohort:
            projected = _project(row, mechanical_names, artifact["normalization_by_intent"][intent])
            raw = _predict(artifact["models_by_intent"][intent], projected["values"])
            probability = _platt_apply(artifact["calibrators_by_intent"][intent], raw)
            if probability >= artifact["thresholds_by_intent"][intent]:
                selected.append(row)
        correct = sum(int(row["target"]) for row in selected)
        total = len(selected)
        precision = correct / total if total else 0.0
        wilson = _wilson(correct, total)
        difficulty_metrics = {}
        difficulty_safe = True
        for difficulty in ("easy", "moderate", "hard"):
            group = [row for row in selected if row.get("difficulty") == difficulty]
            group_correct = sum(int(row["target"]) for row in group)
            group_precision = group_correct / len(group) if group else 0.0
            difficulty_metrics[difficulty] = {
                "selected": len(group), "correct": group_correct, "precision": group_precision,
            }
            if len(group) >= 20 and group_precision < 0.75:
                difficulty_safe = False
        champion_is_enriched = result["comparison"].get(intent, {}).get("champion") == "enriched"
        subgroup_safe, subgroup_violations = _subgroup_safety(selected)
        passed = (
            total >= 20 and precision >= 0.85 and wilson >= 0.75
            and difficulty_safe and subgroup_safe and champion_is_enriched
        )
        metrics[intent] = {
            "holdout_rows": len(cohort), "selected": total, "correct": correct,
            "precision": precision, "coverage": total / len(cohort) if cohort else 0.0,
            "wilson_lower_95": wilson, "difficulty": difficulty_metrics,
            "difficulty_safe": difficulty_safe, "champion_is_enriched": champion_is_enriched,
            "subgroup_safe": subgroup_safe, "subgroup_violations": subgroup_violations,
            "passed": passed,
        }
        if passed:
            passed_intents.append(intent)
    result["promotion"] = {
        "holdout_rows": len(holdout), "metrics": metrics,
        "passed_intents": passed_intents, "holdout_opened_once": True,
    }
    result["artifact"] = {
        **artifact, "default_enabled": bool(passed_intents),
        "allowed_intents": sorted(passed_intents),
        "training_scope": "historical_plus_expansion_development_frozen_before_sealed_holdout",
        "protected_rows_not_used": len(holdout),
    }
    result["decision"] = "promoted" if passed_intents else "rejected_by_sealed_holdout"
    return result


def fit(rows: Sequence[Mapping[str, Any]], mechanical_names: Sequence[str]) -> dict[str, Any]:
    fit_rows = [row for row in rows if row["role"] == "fit" and row["assessment_valid"]]
    calibration_rows = [row for row in rows if row["role"] == "calibration" and row["assessment_valid"]]
    protected = [row for row in rows if row["role"] in {"protected_holdout", "external_audit"}]
    variants = {"score_only": tuple(), "enriched": tuple(mechanical_names)}
    comparison: dict[str, Any] = {}
    artifacts = {}
    thresholds = {}
    normalizations = {}
    allowed = []
    for intent in INTENTS:
        train = [row for row in fit_rows if row["predicted_intent"] == intent]
        calibration = [row for row in calibration_rows if row["predicted_intent"] == intent]
        if len(train) < 40 or len(calibration) < 20:
            comparison[intent] = {"status": "insufficient_support", "train": len(train), "calibration": len(calibration)}
            continue
        intent_result = {}
        variant_models = {}
        for name, mechanical in variants.items():
            dimensions = len(SCORES) + len(mechanical)
            raw_train = [_project(row, mechanical) for row in train]
            normalization = _fit_normalization(raw_train, dimensions)
            projected_train = [_project(row, mechanical, normalization) for row in train]
            projected_calibration = [_project(row, mechanical, normalization) for row in calibration]
            oof = _grouped_oof(projected_train, dimensions)
            weights = _logistic_fit(projected_train, dimensions=dimensions, l2=2.0)
            raw = [_predict(weights, row["values"]) for row in projected_calibration]
            calibrator = _platt_fit(raw, projected_calibration)
            calibrated = [_platt_apply(calibrator, value) for value in raw]
            point = _select_threshold(projected_calibration, calibrated)
            isotonic = _isotonic_fit(raw, projected_calibration) if len(projected_calibration) >= 100 else None
            isotonic_probabilities = (
                [_isotonic_apply(isotonic, value) for value in raw] if isotonic is not None else []
            )
            elastic_weights = _logistic_fit(
                projected_train, dimensions=dimensions, l2=1.0, l1=0.01, iterations=350,
            )
            elastic_raw = [_predict(elastic_weights, row["values"]) for row in projected_calibration]
            elastic_calibrator = _platt_fit(elastic_raw, projected_calibration)
            elastic_probabilities = [_platt_apply(elastic_calibrator, value) for value in elastic_raw]
            nonlinear_train = [{**row, "values": [*row["values"], *(value * value for value in row["values"])]} for row in projected_train]
            nonlinear_calibration = [{**row, "values": [*row["values"], *(value * value for value in row["values"])]} for row in projected_calibration]
            nonlinear_weights = _logistic_fit(
                nonlinear_train, dimensions=dimensions * 2, l2=3.0, iterations=350,
            )
            nonlinear_raw = [_predict(nonlinear_weights, row["values"]) for row in nonlinear_calibration]
            nonlinear_calibrator = _platt_fit(nonlinear_raw, nonlinear_calibration)
            nonlinear_probabilities = [_platt_apply(nonlinear_calibrator, value) for value in nonlinear_raw]
            intent_result[name] = {
                "train_rows": len(train), "calibration_rows": len(calibration),
                "oof_brier": _brier(projected_train, oof),
                "calibration_brier": _brier(projected_calibration, calibrated),
                "calibration_log_loss": _log_loss(projected_calibration, calibrated),
                "calibration_auroc": _auroc(projected_calibration, calibrated),
                "calibration_average_precision": _average_precision(projected_calibration, calibrated),
                "operating_point": point,
                "selected_strata": _selected_strata(projected_calibration, calibrated, point["threshold"]),
                "calibrator_diagnostics": {
                    "production_choice": "platt",
                    "platt": _estimator_metrics(projected_calibration, calibrated),
                    "isotonic": (
                        _estimator_metrics(projected_calibration, isotonic_probabilities)
                        if isotonic_probabilities else {"status": "insufficient_support"}
                    ),
                },
                "estimator_diagnostics": {
                    "ridge_logistic": _estimator_metrics(projected_calibration, calibrated),
                    "elastic_net_logistic": _estimator_metrics(projected_calibration, elastic_probabilities),
                    "quadratic_logistic": _estimator_metrics(nonlinear_calibration, nonlinear_probabilities),
                    "production_choice": "ridge_logistic",
                    "choice_reason": "simplest auditable model retained unless a challenger shows a material held-out gain",
                },
            }
            variant_models[name] = (weights, calibrator)
        enriched = intent_result["enriched"]
        baseline = intent_result["score_only"]
        enriched_better = (
            enriched["calibration_brier"] <= baseline["calibration_brier"] + 0.01
            and enriched["operating_point"]["coverage"] >= baseline["operating_point"]["coverage"]
        )
        champion = "enriched" if enriched_better else "score_only"
        chosen = intent_result[champion]
        weights, calibrator = variant_models[champion]
        # Runtime coefficients include zero-valued mechanical terms when the
        # score-only baseline wins, preserving one strict artifact dimension.
        if champion == "score_only":
            weights = [weights[0], *weights[1:], *([0.0] * len(mechanical_names))]
        artifacts[intent] = {"coefficients": weights, "platt": calibrator, "champion": champion}
        chosen_mechanical = variants[champion]
        chosen_raw_train = [_project(row, chosen_mechanical) for row in train]
        chosen_normalization = _fit_normalization(chosen_raw_train, len(SCORES) + len(chosen_mechanical))
        if champion == "score_only":
            chosen_normalization = {
                "mean": [*chosen_normalization["mean"], *([0.0] * len(mechanical_names))],
                "scale": [*chosen_normalization["scale"], *([1.0] * len(mechanical_names))],
            }
        normalizations[intent] = chosen_normalization
        thresholds[intent] = chosen["operating_point"]["threshold"]
        promoted = bool(chosen["operating_point"]["eligible"])
        if promoted:
            allowed.append(intent)
        comparison[intent] = {
            "status": "nominated" if promoted else "disabled", "champion": champion,
            "score_only": baseline, "enriched": enriched,
        }
    models = {intent: artifacts[intent]["coefficients"] for intent in artifacts}
    # Missing cohorts remain explicit models with a remote-only threshold.
    dimensions = len(SCORES) + len(mechanical_names)
    for intent in INTENTS:
        models.setdefault(intent, [-60.0] + [0.0] * dimensions)
        thresholds.setdefault(intent, 1.0)
        normalizations.setdefault(intent, {"mean": [0.0] * dimensions, "scale": [1.0] * dimensions})
    calibrators = {
        intent: artifacts.get(intent, {"platt": [1.0, 0.0]})["platt"]
        for intent in INTENTS
    }
    artifact = {
        "schema_version": "e2b-category-matrix-regression-v2",
        "default_enabled": False,
        "decision_threshold": 1.0,
        "invalid_270m_route": "fireworks",
        "score_feature_names": list(SCORES),
        "mechanical_feature_names": list(mechanical_names),
        "models_by_intent": models,
        "calibrators_by_intent": calibrators,
        "normalization_by_intent": normalizations,
        "thresholds_by_intent": thresholds,
        "allowed_intents": sorted(allowed),
        "training_scope": "historical_fit_and_calibration_only_expansion_not_yet_available",
        "fit_rows": len(fit_rows), "calibration_rows": len(calibration_rows),
        "protected_rows_not_used": len(protected),
    }
    return {
        "schema_version": "e2b-category-calibration-report-v2",
        "population": {"fit": len(fit_rows), "calibration": len(calibration_rows), "protected": len(protected)},
        "comparison": comparison, "artifact": artifact,
        "decision": "candidate_disabled_pending_expansion_and_sealed_holdout",
    }


def _project(
    row: Mapping[str, Any], mechanical_names: Sequence[str],
    normalization: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, Any]:
    values = [float(row["scores"][name]) / 10.0 for name in SCORES]
    values.extend(float(row["mechanical_features"][name]) for name in mechanical_names)
    if normalization is not None:
        means = normalization["mean"]
        scales = normalization["scale"]
        values = [
            (value - float(mean)) / float(scale)
            for value, mean, scale in zip(values, means, scales, strict=True)
        ]
    return {**row, "values": values}


def _fit_normalization(rows: Sequence[Mapping[str, Any]], dimensions: int) -> dict[str, list[float]]:
    if not rows:
        return {"mean": [0.0] * dimensions, "scale": [1.0] * dimensions}
    columns = [[float(row["values"][index]) for row in rows] for index in range(dimensions)]
    means = [statistics.fmean(column) for column in columns]
    scales = [statistics.pstdev(column) or 1.0 for column in columns]
    return {"mean": means, "scale": scales}


def _grouped_oof(rows: Sequence[Mapping[str, Any]], dimensions: int) -> list[float]:
    folds = [_fold(str(row["source"]), str(row["mutation_lineage"])) for row in rows]
    predictions = [0.0] * len(rows)
    for fold in range(FOLDS):
        train = [row for row, assigned in zip(rows, folds, strict=True) if assigned != fold]
        held = [(index, row) for index, (row, assigned) in enumerate(zip(rows, folds, strict=True)) if assigned == fold]
        if not train or not held:
            continue
        weights = _logistic_fit(train, dimensions=dimensions, l2=2.0)
        for index, row in held:
            predictions[index] = _predict(weights, row["values"])
    return predictions


def _logistic_fit(
    rows: Sequence[Mapping[str, Any]], *, dimensions: int, l2: float,
    iterations: int = 700, balanced: bool = True, l1: float = 0.0,
) -> list[float]:
    if np is not None:
        matrix = np.asarray([[1.0, *row["values"]] for row in rows], dtype=float)
        targets = np.asarray([float(row["target"]) for row in rows], dtype=float)
        sample_weights = _class_weights(targets.tolist()) if balanced else [1.0] * len(rows)
        weights_array = np.asarray(sample_weights, dtype=float)
        coefficients = np.zeros(dimensions + 1, dtype=float)
        penalty_mask = np.ones(dimensions + 1, dtype=float)
        penalty_mask[0] = 0.0
        for iteration in range(iterations):
            logits = np.clip(matrix @ coefficients, -60.0, 60.0)
            predictions = 1.0 / (1.0 + np.exp(-logits))
            gradient = matrix.T @ ((predictions - targets) * weights_array)
            rate = 0.3 / math.sqrt(1 + iteration / 100)
            coefficients -= rate * (gradient + l2 * coefficients * penalty_mask) / max(1, len(rows))
            if l1:
                shrink = rate * l1 / max(1, len(rows))
                coefficients[1:] = np.sign(coefficients[1:]) * np.maximum(0.0, np.abs(coefficients[1:]) - shrink)
        return coefficients.tolist()
    weights = [0.0] * (dimensions + 1)
    sample_weights = _class_weights([float(row["target"]) for row in rows]) if balanced else [1.0] * len(rows)
    for iteration in range(iterations):
        gradient = [0.0] * len(weights)
        for row, sample_weight in zip(rows, sample_weights, strict=True):
            x = [1.0, *row["values"]]
            error = (_predict(weights, row["values"]) - float(row["target"])) * sample_weight
            for index, value in enumerate(x):
                gradient[index] += error * value
        rate = 0.3 / math.sqrt(1 + iteration / 100)
        for index in range(len(weights)):
            penalty = 0.0 if index == 0 else l2 * weights[index]
            weights[index] -= rate * (gradient[index] + penalty) / max(1, len(rows))
            if index and l1:
                shrink = rate * l1 / max(1, len(rows))
                weights[index] = math.copysign(max(0.0, abs(weights[index]) - shrink), weights[index])
    return weights


def _class_weights(targets: Sequence[float]) -> list[float]:
    positives = sum(value >= 0.5 for value in targets)
    negatives = len(targets) - positives
    if not positives or not negatives:
        return [1.0] * len(targets)
    positive_weight = len(targets) / (2.0 * positives)
    negative_weight = len(targets) / (2.0 * negatives)
    return [positive_weight if value >= 0.5 else negative_weight for value in targets]


def _estimator_metrics(rows: Sequence[Mapping[str, Any]], probabilities: Sequence[float]) -> dict[str, float]:
    return {
        "brier": _brier(rows, probabilities),
        "log_loss": _log_loss(rows, probabilities),
        "auroc": _auroc(rows, probabilities),
        "average_precision": _average_precision(rows, probabilities),
    }


def _predict(weights: Sequence[float], values: Sequence[float]) -> float:
    logit = weights[0] + sum(weight * value for weight, value in zip(weights[1:], values, strict=True))
    return 1 / (1 + math.exp(-max(-60.0, min(60.0, logit))))


def _platt_fit(probabilities: Sequence[float], rows: Sequence[Mapping[str, Any]]) -> list[float]:
    transformed = [{**row, "values": [_logit(value)]} for row, value in zip(rows, probabilities, strict=True)]
    return _logistic_fit(transformed, dimensions=1, l2=0.5, iterations=500, balanced=False)


def _platt_apply(weights: Sequence[float], probability: float) -> float:
    return _predict(weights, [_logit(probability)])


def _isotonic_fit(
    probabilities: Sequence[float], rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    ordered = sorted((float(probability), float(row["target"])) for probability, row in zip(probabilities, rows, strict=True))
    blocks: list[dict[str, float]] = []
    for probability, target in ordered:
        blocks.append({"upper": probability, "sum": target, "count": 1.0})
        while len(blocks) >= 2:
            left, right = blocks[-2], blocks[-1]
            if left["sum"] / left["count"] <= right["sum"] / right["count"]:
                break
            blocks[-2:] = [{
                "upper": right["upper"],
                "sum": left["sum"] + right["sum"],
                "count": left["count"] + right["count"],
            }]
    return (
        tuple(block["upper"] for block in blocks),
        tuple(block["sum"] / block["count"] for block in blocks),
    )


def _isotonic_apply(model: tuple[Sequence[float], Sequence[float]], probability: float) -> float:
    upper, values = model
    index = min(len(values) - 1, bisect.bisect_left(upper, probability))
    return float(values[index])


def _logit(value: float) -> float:
    bounded = min(1 - 1e-6, max(1e-6, value))
    return math.log(bounded / (1 - bounded))


def _select_threshold(rows: Sequence[Mapping[str, Any]], probabilities: Sequence[float]) -> dict[str, Any]:
    candidates = sorted(set(round(value, 6) for value in probabilities), reverse=True)
    points = []
    for threshold in candidates:
        selected = [row for row, probability in zip(rows, probabilities, strict=True) if probability >= threshold]
        correct = sum(int(row["target"]) for row in selected)
        total = len(selected)
        precision = correct / total if total else 0.0
        subgroup_safe, subgroup_violations = _subgroup_safety(selected)
        points.append({
            "threshold": threshold, "selected": total, "correct": correct,
            "precision": precision, "coverage": total / len(rows),
            "false_positive_rate": (total - correct) / max(1, sum(not int(row["target"]) for row in rows)),
            "wilson_lower_95": _wilson(correct, total),
            "subgroup_safe": subgroup_safe, "subgroup_violations": subgroup_violations,
            "eligible": total >= 20 and precision >= 0.85 and _wilson(correct, total) >= 0.70 and subgroup_safe,
        })
    eligible = [point for point in points if point["eligible"]]
    return max(eligible, key=lambda point: (point["coverage"], point["precision"])) if eligible else {
        "threshold": 1.0, "selected": 0, "correct": 0, "precision": 0.0,
        "coverage": 0.0, "false_positive_rate": 0.0, "wilson_lower_95": 0.0,
        "subgroup_safe": False, "subgroup_violations": [], "eligible": False,
    }


def _subgroup_safety(rows: Sequence[Mapping[str, Any]]) -> tuple[bool, list[dict[str, Any]]]:
    dimensions = {
        "source": lambda row: str(row.get("source") or "unknown"),
        "difficulty": lambda row: str(row.get("difficulty") or "unknown"),
        "provider": lambda row: str(row.get("generator_provider") or "unknown"),
        "language": _row_language,
        "output_shape": _row_output_shape,
    }
    violations = []
    for dimension, extractor in dimensions.items():
        groups: dict[str, list[Mapping[str, Any]]] = {}
        for row in rows:
            groups.setdefault(extractor(row), []).append(row)
        for value, group in groups.items():
            precision = sum(int(row["target"]) for row in group) / len(group)
            if len(group) >= 20 and precision < 0.75:
                violations.append({
                    "dimension": dimension, "value": value,
                    "support": len(group), "precision": precision,
                })
    return not violations, violations


def _brier(rows: Sequence[Mapping[str, Any]], probabilities: Sequence[float]) -> float:
    return statistics.fmean((probability - float(row["target"])) ** 2 for row, probability in zip(rows, probabilities, strict=True))


def _log_loss(rows: Sequence[Mapping[str, Any]], probabilities: Sequence[float]) -> float:
    return statistics.fmean(
        -(float(row["target"]) * math.log(max(1e-9, probability)) + (1 - float(row["target"])) * math.log(max(1e-9, 1 - probability)))
        for row, probability in zip(rows, probabilities, strict=True)
    )


def _auroc(rows: Sequence[Mapping[str, Any]], probabilities: Sequence[float]) -> float:
    positives = sum(int(row["target"]) for row in rows)
    negatives = len(rows) - positives
    if not positives or not negatives:
        return 0.5
    ranked = sorted(zip(probabilities, rows, strict=True), key=lambda item: item[0])
    rank_sum = sum(index for index, (_, row) in enumerate(ranked, start=1) if int(row["target"]))
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def _average_precision(rows: Sequence[Mapping[str, Any]], probabilities: Sequence[float]) -> float:
    ranked = sorted(zip(probabilities, rows, strict=True), key=lambda item: item[0], reverse=True)
    positives = sum(int(row["target"]) for row in rows)
    if not positives:
        return 0.0
    correct = 0
    accumulated = 0.0
    for index, (_, row) in enumerate(ranked, start=1):
        if int(row["target"]):
            correct += 1
            accumulated += correct / index
    return accumulated / positives


def _selected_strata(
    rows: Sequence[Mapping[str, Any]], probabilities: Sequence[float], threshold: float,
) -> dict[str, dict[str, dict[str, float | int]]]:
    selected = [row for row, probability in zip(rows, probabilities, strict=True) if probability >= threshold]
    dimensions = {
        "source": lambda row: str(row.get("source") or "unknown"),
        "difficulty": lambda row: str(row.get("difficulty") or "unknown"),
        "provider": lambda row: str(row.get("generator_provider") or "unknown"),
        "language": _row_language,
        "output_shape": _row_output_shape,
    }
    report = {}
    for name, extractor in dimensions.items():
        groups: dict[str, list[Mapping[str, Any]]] = {}
        for row in selected:
            groups.setdefault(extractor(row), []).append(row)
        report[name] = {
            key: {
                "selected": len(group),
                "correct": sum(int(row["target"]) for row in group),
                "precision": sum(int(row["target"]) for row in group) / len(group),
            }
            for key, group in sorted(groups.items())
        }
    return report


def _row_language(row: Mapping[str, Any]) -> str:
    features = row.get("mechanical_features", {})
    for language in ("en", "pt", "es", "other"):
        if float(features.get(f"mechanical.language_{language}", 0.0)) >= 0.5:
            return language
    return "unknown"


def _row_output_shape(row: Mapping[str, Any]) -> str:
    for name, value in row.get("mechanical_features", {}).items():
        if name.startswith("mechanical.shape.") and float(value) >= 0.5:
            return name.rsplit(".", 1)[-1]
    return "unknown"


def _wilson(correct: int, total: int) -> float:
    if not total:
        return 0.0
    z, p = 1.959963984540054, correct / total
    denominator = 1 + z * z / total
    center = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (center - margin) / denominator


def _fold(source: str, lineage: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{source}:{lineage}".encode()).digest()[:4], "big") % FOLDS


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _artifact_sha256(artifact: Mapping[str, Any]) -> str:
    canonical = json.dumps(artifact, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _decision_surface_sha256(artifact: Mapping[str, Any]) -> str:
    decision_surface = {
        key: value for key, value in artifact.items()
        if key not in {"protected_rows_not_used"}
    }
    return _artifact_sha256(decision_surface)


def _markdown(result: Mapping[str, Any]) -> str:
    lines = [
        "# E2B Category Calibration V2", "",
        f"- Fit rows: `{result['population']['fit']}`",
        f"- Calibration rows: `{result['population']['calibration']}`",
        f"- Protected rows not used: `{result['population']['protected']}`", "",
        "## Category Candidates", "",
    ]
    for intent in INTENTS:
        item = result["comparison"].get(intent, {})
        if item.get("champion"):
            point = item[item["champion"]]["operating_point"]
            lines.append(
                f"- `{intent}`: {item['status']}, champion `{item['champion']}`, "
                f"precision `{point['precision']:.2%}`, coverage `{point['coverage']:.2%}`, "
                f"Wilson lower `{point['wilson_lower_95']:.2%}`"
            )
        else:
            lines.append(f"- `{intent}`: {item.get('status', 'missing')}")
    promotion = result.get("promotion")
    if isinstance(promotion, Mapping):
        lines.extend(["", "## Sealed Holdout", ""])
        for intent in result["comparison"]:
            metrics = promotion.get("metrics", {}).get(intent)
            if not isinstance(metrics, Mapping):
                continue
            lines.append(
                f"- `{intent}`: {'promoted' if metrics['passed'] else 'rejected'}, "
                f"selected `{metrics['selected']}`, precision `{metrics['precision']:.2%}`, "
                f"Wilson lower `{metrics['wilson_lower_95']:.2%}`"
            )
        lines.extend([
            "",
            "The holdout was opened once after the candidate decision surface was hash-frozen. "
            "Only categories that passed every support, precision, Wilson and subgroup gate are enabled.",
            "",
        ])
    else:
        lines.extend(["", "The artifact remains disabled until expansion inference, adjudication and sealed-holdout promotion are complete.", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
