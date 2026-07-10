from __future__ import annotations

from statistics import mean
from typing import Any, Mapping, Sequence

from router.core.contracts import TaskAssessment
from router.functiongemma.tooling import SCORE_FIELDS


def assessment_metrics(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("At least one evaluation row is required.")
    valid = [row for row in rows if row.get("prediction") is not None]
    metric: dict[str, Any] = {
        "examples": len(rows),
        "schema_valid": len(valid),
        "schema_validity": len(valid) / len(rows),
        "intent_accuracy": 0.0,
        "valid_only_intent_accuracy": None,
        "score_mae": {name: None for name in SCORE_FIELDS},
        "valid_only_score_mae": {name: None for name in SCORE_FIELDS},
        "weighted_quadratic_kappa": {name: None for name in SCORE_FIELDS},
    }
    if not valid:
        metric["score_mae"] = {name: 10.0 for name in SCORE_FIELDS}
        return metric
    parsed = [
        (TaskAssessment.from_mapping(row["gold"]), TaskAssessment.from_mapping(row["prediction"]))
        for row in valid
    ]
    valid_intent_accuracy = mean(float(gold.intent is prediction.intent) for gold, prediction in parsed)
    valid_fraction = len(valid) / len(rows)
    metric["intent_accuracy"] = valid_intent_accuracy * valid_fraction
    metric["valid_only_intent_accuracy"] = valid_intent_accuracy
    for name in SCORE_FIELDS:
        pairs = [(getattr(prediction.scores, name), getattr(gold.scores, name)) for gold, prediction in parsed]
        valid_absolute_error = sum(abs(prediction - gold) for prediction, gold in pairs)
        metric["score_mae"][name] = (valid_absolute_error + 10 * (len(rows) - len(valid))) / len(rows)
        metric["valid_only_score_mae"][name] = valid_absolute_error / len(valid)
        metric["weighted_quadratic_kappa"][name] = weighted_quadratic_kappa(pairs)
    return metric


def weighted_quadratic_kappa(pairs: list[tuple[int, int]], *, categories: int = 11) -> float | None:
    if not pairs:
        return None
    observed = [[0.0 for _ in range(categories)] for _ in range(categories)]
    left_counts = [0.0] * categories
    right_counts = [0.0] * categories
    for left, right in pairs:
        observed[left][right] += 1
        left_counts[left] += 1
        right_counts[right] += 1
    total = float(len(pairs))
    denominator = float((categories - 1) ** 2)
    weighted_observed = 0.0
    weighted_expected = 0.0
    for left in range(categories):
        for right in range(categories):
            weight = ((left - right) ** 2) / denominator
            weighted_observed += weight * observed[left][right] / total
            weighted_expected += weight * (left_counts[left] * right_counts[right]) / (total * total)
    if weighted_expected == 0:
        return 1.0 if weighted_observed == 0 else 0.0
    return 1.0 - weighted_observed / weighted_expected


def boundary_ordering_metrics(
    tasks: Sequence[Mapping[str, Any]],
    predictions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    predictions_by_id = {str(row["id"]): row.get("prediction") for row in predictions}
    groups: dict[tuple[str, str], list[tuple[int, Mapping[str, Any] | None]]] = {}
    for row in tasks:
        lineage = row.get("mutation_lineage")
        dimension = row.get("boundary_dimension")
        anchor = row.get("boundary_anchor")
        if not isinstance(lineage, str) or dimension not in SCORE_FIELDS:
            continue
        if isinstance(anchor, bool) or not isinstance(anchor, int) or not 0 <= anchor <= 10:
            continue
        groups.setdefault((lineage, str(dimension)), []).append(
            (anchor, predictions_by_id.get(str(row["id"])))
        )
    per_dimension = {
        name: {"comparisons": 0, "concordant": 0, "ties": 0, "inversions": 0, "invalid": 0}
        for name in SCORE_FIELDS
    }
    for (_, dimension), rows in groups.items():
        for left_index, (left_anchor, left_prediction) in enumerate(rows):
            for right_anchor, right_prediction in rows[left_index + 1 :]:
                if left_anchor == right_anchor:
                    continue
                metric = per_dimension[dimension]
                metric["comparisons"] += 1
                if not isinstance(left_prediction, Mapping) or not isinstance(right_prediction, Mapping):
                    metric["invalid"] += 1
                    continue
                left_scores = left_prediction.get("scores")
                right_scores = right_prediction.get("scores")
                if not isinstance(left_scores, Mapping) or not isinstance(right_scores, Mapping):
                    metric["invalid"] += 1
                    continue
                left_score = left_scores.get(dimension)
                right_score = right_scores.get(dimension)
                if not isinstance(left_score, int) or not isinstance(right_score, int):
                    metric["invalid"] += 1
                    continue
                anchor_delta = left_anchor - right_anchor
                prediction_delta = left_score - right_score
                if prediction_delta == 0:
                    metric["ties"] += 1
                elif anchor_delta * prediction_delta > 0:
                    metric["concordant"] += 1
                else:
                    metric["inversions"] += 1
    totals = {
        name: sum(int(metric[name]) for metric in per_dimension.values())
        for name in ("comparisons", "concordant", "ties", "inversions", "invalid")
    }
    for metric in (*per_dimension.values(), totals):
        comparisons = int(metric["comparisons"])
        valid = comparisons - int(metric["invalid"])
        metric["strict_accuracy"] = int(metric["concordant"]) / comparisons if comparisons else None
        metric["valid_only_strict_accuracy"] = int(metric["concordant"]) / valid if valid else None
        metric["tie_adjusted_accuracy"] = (
            (int(metric["concordant"]) + 0.5 * int(metric["ties"])) / comparisons if comparisons else None
        )
    return {
        "schema_version": "functiongemma-boundary-ordering-v1",
        "grouping": "mutation_lineage+boundary_dimension",
        "totals": totals,
        "dimensions": per_dimension,
    }
