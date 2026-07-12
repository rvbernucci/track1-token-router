#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmark_teacher_gate_ml import RUNTIME_SCORE_FEATURES, _rows, _runtime_prediction_rows


ROOT = Path(__file__).resolve().parents[1]
COMPACT_MECHANICAL = (
    "mechanical.ambiguity", "mechanical.code_present", "mechanical.currentness",
    "mechanical.entity_type_count", "mechanical.external_knowledge",
    "mechanical.json_requested", "mechanical.number_density",
    "mechanical.operator_count", "mechanical.prompt_tokens_log",
    "mechanical.shape.boolean", "mechanical.shape.code", "mechanical.shape.free_text",
    "mechanical.shape.json", "mechanical.shape.list", "mechanical.shape.number",
    "mechanical.shape.short_text", "mechanical.strict_format",
    "mechanical.verifier.closed_label", "mechanical.verifier.code_syntax",
    "mechanical.verifier.json_structure", "mechanical.verifier.numeric",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fit per-intent E2B regression with frozen cluster features.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import numpy as np
    from sklearn.cluster import KMeans
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        average_precision_score, brier_score_loss, log_loss, roc_auc_score, silhouette_score,
    )
    from sklearn.preprocessing import StandardScaler

    ledger = _rows(ROOT / "reports/generated/e2b-expansion-v1/regression-ledger.jsonl")
    rows = _runtime_prediction_rows(ledger, _rows(_absolute(args.predictions)), allow_subset=True)
    missing = [name for name in COMPACT_MECHANICAL if name not in rows[0]["mechanical_features"]]
    if missing:
        raise ValueError(f"Compact mechanical contract is missing: {missing}")

    def base_matrix(population: Sequence[Mapping[str, Any]]) -> Any:
        return np.asarray([
            [
                *(float(row["semantic_features"][name]) / 10.0 for name in RUNTIME_SCORE_FEATURES),
                *(float(row["mechanical_features"][name]) for name in COMPACT_MECHANICAL),
            ]
            for row in population
        ], dtype=float)

    by_intent: dict[str, Any] = {}
    runtime: dict[str, Any] = {}
    for intent in sorted({str(row["teacher_intent"]) for row in rows}):
        fit = _intent_role(rows, intent, "fit")
        calibration = _intent_role(rows, intent, "calibration")
        protected = [
            row for row in rows
            if row["teacher_intent"] == intent and row["role"] in {"protected_holdout", "external_audit"}
        ]
        if min(len(fit), len(calibration)) < 20 or len({int(row["target"]) for row in fit}) < 2:
            by_intent[intent] = {"status": "insufficient_support"}
            continue

        geometry_scaler = StandardScaler().fit(base_matrix(fit))
        fit_geometry = geometry_scaler.transform(base_matrix(fit))
        cluster_count = _choose_clusters(fit_geometry, KMeans, silhouette_score)
        clusterer = KMeans(n_clusters=cluster_count, n_init=20, random_state=72).fit(fit_geometry)
        centroids = clusterer.cluster_centers_
        fit_distances = np.linalg.norm(fit_geometry[:, None, :] - centroids[None, :, :], axis=2)
        fit_labels = fit_distances.argmin(axis=1)
        radii = np.asarray([
            max(float(np.quantile(fit_distances[fit_labels == label, label], 0.95)), 1e-9)
            for label in range(cluster_count)
        ])

        def cluster_features(population: Sequence[Mapping[str, Any]]) -> Any:
            values = geometry_scaler.transform(base_matrix(population))
            distances = np.linalg.norm(values[:, None, :] - centroids[None, :, :], axis=2)
            labels = distances.argmin(axis=1)
            nearest = distances[np.arange(len(values)), labels]
            ratio = nearest / radii[labels]
            one_hot = np.eye(cluster_count)[labels]
            return np.column_stack((one_hot, nearest, ratio, (ratio > 1.0).astype(float)))

        variants = {
            "base": lambda population: base_matrix(population),
            "cluster_augmented": lambda population: np.column_stack((base_matrix(population), cluster_features(population))),
        }
        results: dict[str, Any] = {}
        fitted: dict[str, Any] = {}
        for name, matrix in variants.items():
            train_x, calibration_x = matrix(fit), matrix(calibration)
            scaler = StandardScaler().fit(train_x)
            model = LogisticRegression(
                C=0.5, class_weight="balanced", max_iter=3000, random_state=72,
            ).fit(scaler.transform(train_x), _targets(fit))
            probabilities = model.predict_proba(scaler.transform(calibration_x))[:, 1]
            point = _threshold(calibration, probabilities)
            results[name] = {
                "calibration": _probability_metrics(
                    calibration, probabilities, brier_score_loss, log_loss,
                    roc_auc_score, average_precision_score,
                ),
                "operating_point": point,
            }
            fitted[name] = (model, scaler, matrix)

        base, augmented = results["base"], results["cluster_augmented"]
        augmented_nominated = bool(
            augmented["operating_point"]["eligible"]
            and (
                augmented["operating_point"]["selected"] > base["operating_point"]["selected"]
                or augmented["calibration"]["brier"] + 0.005 < base["calibration"]["brier"]
            )
            and augmented["operating_point"]["precision"]
                >= base["operating_point"]["precision"] - 0.01
        )
        champion = "cluster_augmented" if augmented_nominated else "base"
        model, scaler, matrix = fitted[champion]
        audit = _audit(
            protected, model.predict_proba(scaler.transform(matrix(protected)))[:, 1]
            if protected else [], results[champion]["operating_point"]["threshold"],
        )
        protected_safe = _protected_safe(audit)
        promoted = champion == "cluster_augmented" and protected_safe
        by_intent[intent] = {
            "status": "promoted" if promoted else "rejected",
            "champion": champion,
            "cluster_count": cluster_count,
            "base": base,
            "cluster_augmented": augmented,
            "protected": audit,
            "protected_safe": protected_safe,
        }
        if promoted:
            runtime[intent] = {
                "threshold": results[champion]["operating_point"]["threshold"],
                "coefficients": [float(model.intercept_[0]), *(float(value) for value in model.coef_[0])],
                "normalization": {
                    "mean": [float(value) for value in scaler.mean_],
                    "scale": [float(value) for value in scaler.scale_],
                },
                "geometry": {
                    "input_normalization": {
                        "mean": [float(value) for value in geometry_scaler.mean_],
                        "scale": [float(value) for value in geometry_scaler.scale_],
                    },
                    "centroids": [[float(value) for value in centroid] for centroid in centroids],
                    "radii": [float(value) for value in radii],
                },
            }

    payload = {
        "schema_version": "e2b-cluster-augmented-benchmark-v1",
        "rows": len(rows),
        "prediction_union_sha256": _sha256(_absolute(args.predictions)),
        "geometry_fit_scope": "fit_only",
        "threshold_scope": "calibration_only",
        "protected_scope": "audit_only",
        "base_feature_names": [*RUNTIME_SCORE_FEATURES, *COMPACT_MECHANICAL],
        "cluster_feature_contract": "one_hot + nearest_distance + radius_ratio + outlier",
        "runtime_candidates": runtime,
        "by_intent": by_intent,
    }
    output = _absolute(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "rows": len(rows), "promoted_intents": sorted(runtime),
        "decisions": {intent: value["status"] for intent, value in by_intent.items()},
    }, sort_keys=True))
    return 0


def _choose_clusters(values: Any, kmeans: Any, silhouette: Any) -> int:
    candidates = [value for value in (3, 4, 6, 8) if value < len(values)]
    scored = []
    for count in candidates:
        labels = kmeans(n_clusters=count, n_init=20, random_state=72).fit_predict(values)
        scored.append((float(silhouette(values, labels)), -count, count))
    return max(scored)[2]


def _threshold(rows: Sequence[Mapping[str, Any]], probabilities: Sequence[float]) -> dict[str, Any]:
    best = None
    for threshold in sorted({round(float(value), 6) for value in probabilities}):
        selected = [row for row, probability in zip(rows, probabilities, strict=True) if probability >= threshold]
        correct, total = sum(int(row["target"]) for row in selected), len(selected)
        precision = correct / total if total else 0.0
        candidate = {
            "threshold": threshold, "selected": total, "correct": correct,
            "coverage": total / len(rows), "precision": precision,
            "wilson_lower_95": _wilson(correct, total),
            "eligible": total >= 20 and precision >= 0.90 and _wilson(correct, total) >= 0.75,
        }
        if candidate["eligible"] and (best is None or (total, precision) > (best["selected"], best["precision"])):
            best = candidate
    return best or {
        "threshold": 1.0, "selected": 0, "correct": 0, "coverage": 0.0,
        "precision": 0.0, "wilson_lower_95": 0.0, "eligible": False,
    }


def _audit(rows: Sequence[Mapping[str, Any]], probabilities: Sequence[float], threshold: float) -> dict[str, Any]:
    sets = {"all_protected": list(rows)}
    for source in sorted({str(row["source"]) for row in rows}):
        sets[source] = [row for row in rows if row["source"] == source]
    result = {}
    for name, population in sets.items():
        selected = [row for row, probability in zip(rows, probabilities, strict=True)
                    if row in population and probability >= threshold]
        correct = sum(int(row["target"]) for row in selected)
        result[name] = {
            "population": len(population), "selected": len(selected), "correct": correct,
            "coverage": len(selected) / len(population) if population else 0.0,
            "precision": correct / len(selected) if selected else 0.0,
            "wilson_lower_95": _wilson(correct, len(selected)),
        }
    return result


def _protected_safe(audit: Mapping[str, Mapping[str, Any]]) -> bool:
    overall = audit["all_protected"]
    if overall["selected"] < 20 or overall["precision"] < 0.85:
        return False
    return all(item["selected"] < 20 or item["precision"] >= 0.85 for item in audit.values())


def _probability_metrics(rows: Sequence[Mapping[str, Any]], probabilities: Any, brier: Any, loss: Any, auroc: Any, average_precision: Any) -> dict[str, float]:
    targets = _targets(rows)
    return {
        "brier": float(brier(targets, probabilities)),
        "log_loss": float(loss(targets, probabilities, labels=[0, 1])),
        "auroc": float(auroc(targets, probabilities)) if len(set(targets)) == 2 else 0.5,
        "average_precision": float(average_precision(targets, probabilities)),
        "calibration_error": _calibration_error(targets, probabilities),
    }


def _calibration_error(targets: Sequence[int], probabilities: Sequence[float]) -> float:
    bins = [[] for _ in range(10)]
    for target, probability in zip(targets, probabilities, strict=True):
        bins[min(9, int(float(probability) * 10))].append((target, float(probability)))
    total = len(targets)
    return sum(
        len(bucket) / total * abs(sum(item[0] for item in bucket) / len(bucket) - sum(item[1] for item in bucket) / len(bucket))
        for bucket in bins if bucket
    )


def _targets(rows: Sequence[Mapping[str, Any]]) -> list[int]:
    return [int(row["target"]) for row in rows]


def _intent_role(rows: Sequence[Mapping[str, Any]], intent: str, role: str) -> list[Mapping[str, Any]]:
    return [row for row in rows if row["teacher_intent"] == intent and row["role"] == role]


def _wilson(correct: int, total: int) -> float:
    if not total:
        return 0.0
    z, p = 1.959963984540054, correct / total
    denominator = 1 + z * z / total
    return (p + z * z / (2 * total) - z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)) / denominator


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
