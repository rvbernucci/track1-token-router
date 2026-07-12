#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_functiongemma_teacher_consensus import _teacher_items as _load_teacher_items


SEMANTIC_FEATURES = (
    "difficulty", "reasoning_demand", "generation_demand", "knowledge_requirement",
    "ambiguity", "deterministic_fit",
)
RUNTIME_SCORE_FEATURES = (
    "deterministic_fit", "reasoning_demand", "knowledge_uncertainty",
    "generation_demand", "format_complexity",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark ML gates on teacher-consensus semantics.")
    parser.add_argument(
        "--teacher-root", type=Path, default=Path("reports/generated/semantic-teacher-relabel-v1"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/generated/semantic-teacher-gate-benchmark.json"),
    )
    parser.add_argument("--minimum-confidence", type=int, default=70)
    parser.add_argument(
        "--predictions", type=Path,
        help="Use runtime FunctionGemma predictions instead of teacher semantic labels.",
    )
    args = parser.parse_args()
    try:
        import numpy as np
        from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise RuntimeError("Research benchmark requires numpy and scikit-learn.") from exc

    ledger = _rows(ROOT / "reports/generated/e2b-expansion-v1/regression-ledger.jsonl")
    if args.predictions:
        rows = _runtime_prediction_rows(ledger, _rows(_absolute(args.predictions)))
        semantic_features = RUNTIME_SCORE_FEATURES
        teacher_overlap = None
        primary_teacher_breakdown = None
        feature_source = "functiongemma_runtime_predictions"
    else:
        teacher_root = _absolute(args.teacher_root)
        agy = _load_teacher_items(teacher_root / "agy-batches.jsonl")
        codex_path = teacher_root / "codex-fill-batches.jsonl"
        codex_fill = _load_teacher_items(codex_path) if codex_path.is_file() else {}
        semantic_primary = {**codex_fill, **agy}
        kimi = _load_teacher_items(teacher_root / "kimi-batches.jsonl")
        rows = _consensus_rows(ledger, semantic_primary, kimi, args.minimum_confidence)
        semantic_features = SEMANTIC_FEATURES
        teacher_overlap = len(set(semantic_primary) & set(kimi))
        primary_teacher_breakdown = {"agy": len(agy), "codex_fill": len(codex_fill)}
        feature_source = "teacher_consensus"
    mechanical_names = tuple(sorted(rows[0]["mechanical_features"]))

    def matrix(population: Sequence[Mapping[str, Any]]) -> Any:
        return np.asarray([
            [
                *(float(row["semantic_features"][name]) / (4.0 if name == "difficulty" else 10.0)
                  for name in semantic_features),
                *(float(row["mechanical_features"][name]) for name in mechanical_names),
            ]
            for row in population
        ], dtype=float)

    factories: dict[str, Callable[[], Any]] = {
        "ridge_logistic": lambda: make_pipeline(
            StandardScaler(), LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000),
        ),
        "hist_gradient_boosting": lambda: HistGradientBoostingClassifier(
            max_iter=180, max_leaf_nodes=15, learning_rate=0.05,
            l2_regularization=2.0, class_weight="balanced", random_state=72,
        ),
        "extra_trees": lambda: ExtraTreesClassifier(
            n_estimators=400, max_depth=10, min_samples_leaf=8, max_features=0.7,
            class_weight="balanced", random_state=72, n_jobs=-1,
        ),
    }
    intents = sorted({str(row["teacher_intent"]) for row in rows})
    evaluations = {}
    for model_name, factory in factories.items():
        models = {}
        for intent in intents:
            train = [row for row in rows if row["role"] == "fit" and row["teacher_intent"] == intent]
            calibration = [
                row for row in rows if row["role"] == "calibration" and row["teacher_intent"] == intent
            ]
            if not _binary_support(train) or not _binary_support(calibration):
                continue
            model = factory()
            model.fit(matrix(train), np.asarray([row["target"] for row in train], dtype=int))
            probabilities = model.predict_proba(matrix(calibration))[:, 1]
            point = _threshold([int(row["target"]) for row in calibration], probabilities.tolist())
            if point is not None:
                models[intent] = (model, float(point["threshold"]))
        evaluations[model_name] = {
            "enabled_intents": sorted(models),
            "runtime_artifacts": (
                {
                    intent: _ridge_artifact(model, threshold)
                    for intent, (model, threshold) in models.items()
                }
                if model_name == "ridge_logistic" else None
            ),
            "sets": {
                name: _evaluate(population, models, matrix)
                for name, population in _evaluation_sets(rows).items()
            },
        }

    payload = {
        "schema_version": "semantic-teacher-gate-benchmark-v1",
        "rows": len(rows),
        "feature_source": feature_source,
        "teacher_overlap": teacher_overlap,
        "primary_teacher_breakdown": primary_teacher_breakdown,
        "feature_count": len(semantic_features) + len(mechanical_names),
        "semantic_features": list(semantic_features),
        "mechanical_features": list(mechanical_names),
        "threshold_policy": "maximize calibration coverage with precision>=0.90, Wilson>=0.75, support>=20",
        "models": evaluations,
    }
    output = _absolute(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({name: result["sets"] for name, result in evaluations.items()}, sort_keys=True))
    return 0


def _consensus_rows(
    ledger: Sequence[Mapping[str, Any]], agy: Mapping[str, Mapping[str, Any]],
    kimi: Mapping[str, Mapping[str, Any]], minimum_confidence: int,
) -> list[dict[str, Any]]:
    rows = []
    for row in ledger:
        task_id = str(row["task_id"])
        left, right = agy.get(task_id), kimi.get(task_id)
        if left is None or right is None or left["intent"] != right["intent"]:
            continue
        if min(int(left["confidence"]), int(right["confidence"])) < minimum_confidence:
            continue
        weights = (max(1, int(left["confidence"])), max(1, int(right["confidence"])))
        semantic = {
            name: (float(left[name]) * weights[0] + float(right[name]) * weights[1]) / sum(weights)
            for name in SEMANTIC_FEATURES
        }
        rows.append({
            **row, "teacher_intent": str(left["intent"]), "semantic_features": semantic,
        })
    if not rows:
        raise ValueError("No valid teacher-consensus rows are available.")
    return rows


def _runtime_prediction_rows(
    ledger: Sequence[Mapping[str, Any]], predictions: Sequence[Mapping[str, Any]],
    *, allow_subset: bool = False,
) -> list[dict[str, Any]]:
    by_id = {str(row["id"]): row for row in predictions}
    if len(by_id) != len(predictions):
        raise ValueError("FunctionGemma predictions contain duplicate IDs.")
    ledger_ids = {str(row["task_id"]) for row in ledger}
    if allow_subset and not set(by_id).issubset(ledger_ids):
        raise ValueError("FunctionGemma prediction IDs must be a subset of the regression ledger.")
    if not allow_subset and set(by_id) != ledger_ids:
        raise ValueError("FunctionGemma prediction IDs must match the regression ledger exactly.")
    rows = []
    for row in ledger:
        if str(row["task_id"]) not in by_id:
            continue
        prediction = by_id[str(row["task_id"])].get("prediction")
        if not isinstance(prediction, Mapping) or not isinstance(prediction.get("scores"), Mapping):
            continue
        scores = prediction["scores"]
        if set(scores) != set(RUNTIME_SCORE_FEATURES):
            raise ValueError("FunctionGemma prediction has an incompatible score contract.")
        rows.append({
            **row,
            "teacher_intent": str(prediction["intent"]),
            "semantic_features": {name: float(scores[name]) for name in RUNTIME_SCORE_FEATURES},
        })
    if not rows:
        raise ValueError("No valid FunctionGemma runtime predictions are available.")
    return rows


def _evaluation_sets(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    return {
        "boundary_external": [row for row in rows if row["source"] == "boundary"],
        "expansion_holdout": [
            row for row in rows if row["source"] == "expansion" and row["role"] == "protected_holdout"
        ],
        "historical_holdout": [
            row for row in rows
            if row["source"] in {"legacy", "v2"} and row["role"] == "protected_holdout"
        ],
        "all_protected": [
            row for row in rows if row["role"] in {"protected_holdout", "external_audit"}
        ],
    }


def _evaluate(population: Sequence[Mapping[str, Any]], models: Mapping[str, Any], matrix: Callable) -> dict[str, Any]:
    selected = []
    for row in population:
        model_and_threshold = models.get(str(row["teacher_intent"]))
        if model_and_threshold is None:
            continue
        model, threshold = model_and_threshold
        probability = float(model.predict_proba(matrix([row]))[0, 1])
        if probability >= threshold:
            selected.append(row)
    result = _metrics(population, selected)
    result["by_teacher_intent"] = {
        intent: _metrics(
            [row for row in population if row["teacher_intent"] == intent],
            [row for row in selected if row["teacher_intent"] == intent],
        )
        for intent in sorted({str(row["teacher_intent"]) for row in population})
    }
    result["by_category"] = {
        category: _metrics(
            [row for row in population if row["category"] == category],
            [row for row in selected if row["category"] == category],
        )
        for category in sorted({str(row["category"]) for row in population})
    }
    return result


def _metrics(population: Sequence[Mapping[str, Any]], selected: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    correct = sum(int(row["target"]) for row in selected)
    return {
        "population": len(population), "selected": len(selected), "correct": correct,
        "precision": correct / len(selected) if selected else 0.0,
        "wilson_lower_95": _wilson(correct, len(selected)),
        "coverage": len(selected) / len(population) if population else 0.0,
    }


def _threshold(labels: Sequence[int], probabilities: Sequence[float]) -> dict[str, float] | None:
    best = None
    for threshold in sorted(set(float(value) for value in probabilities)):
        selected = [label for label, probability in zip(labels, probabilities, strict=True) if probability >= threshold]
        correct, total = sum(selected), len(selected)
        precision = correct / total if total else 0.0
        wilson = _wilson(correct, total)
        if total >= 20 and precision >= 0.90 and wilson >= 0.75:
            candidate = {"threshold": threshold, "selected": total, "precision": precision, "wilson": wilson}
            if best is None or (total, precision, wilson) > (best["selected"], best["precision"], best["wilson"]):
                best = candidate
    return best


def _wilson(correct: int, total: int) -> float:
    if not total:
        return 0.0
    z = 1.959963984540054
    proportion = correct / total
    denominator = 1 + z * z / total
    return (
        proportion + z * z / (2 * total)
        - z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total)
    ) / denominator


def _binary_support(rows: Sequence[Mapping[str, Any]]) -> bool:
    values = {int(row["target"]) for row in rows}
    return len(rows) >= 20 and values == {0, 1}


def _ridge_artifact(model: Any, threshold: float) -> dict[str, Any]:
    scaler = model.named_steps["standardscaler"]
    classifier = model.named_steps["logisticregression"]
    coefficients = classifier.coef_[0].tolist()
    return {
        "coefficients": [float(classifier.intercept_[0]), *(float(value) for value in coefficients)],
        "normalization": {
            "mean": [float(value) for value in scaler.mean_],
            "scale": [float(value) for value in scaler.scale_],
        },
        "threshold": float(threshold),
    }


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
