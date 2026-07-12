#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.benchmark_teacher_gate_ml import (
    RUNTIME_SCORE_FEATURES,
    _rows,
    _runtime_prediction_rows,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover safe E2B subcohorts by runtime-feature clustering.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--feature-profile", choices=("scores", "compact", "full"), default="full")
    args = parser.parse_args()

    import numpy as np
    from sklearn.cluster import DBSCAN, HDBSCAN, KMeans
    from sklearn.preprocessing import StandardScaler

    ledger = _rows(ROOT / "reports/generated/e2b-expansion-v1/regression-ledger.jsonl")
    rows = _runtime_prediction_rows(ledger, _rows(_absolute(args.predictions)), allow_subset=True)
    all_mechanical_names = tuple(sorted(rows[0]["mechanical_features"]))
    compact_names = {
        "mechanical.ambiguity", "mechanical.code_present", "mechanical.currentness",
        "mechanical.entity_type_count", "mechanical.external_knowledge",
        "mechanical.json_requested", "mechanical.number_density",
        "mechanical.operator_count", "mechanical.prompt_tokens_log",
        "mechanical.shape.boolean", "mechanical.shape.code", "mechanical.shape.free_text",
        "mechanical.shape.json", "mechanical.shape.list", "mechanical.shape.number",
        "mechanical.shape.short_text", "mechanical.strict_format",
        "mechanical.verifier.closed_label", "mechanical.verifier.code_syntax",
        "mechanical.verifier.json_structure", "mechanical.verifier.numeric",
    }
    mechanical_names = (
        () if args.feature_profile == "scores"
        else tuple(name for name in all_mechanical_names if name in compact_names)
        if args.feature_profile == "compact" else all_mechanical_names
    )
    feature_names = (*RUNTIME_SCORE_FEATURES, *mechanical_names)

    def matrix(population: Sequence[Mapping[str, Any]]) -> Any:
        return np.asarray([
            [
                *(float(row["semantic_features"][name]) / 10.0 for name in RUNTIME_SCORE_FEATURES),
                *(float(row["mechanical_features"][name]) for name in mechanical_names),
            ]
            for row in population
        ], dtype=float)

    candidates = [
        *(('kmeans', {"clusters": clusters}) for clusters in (3, 4, 6, 8, 10)),
        *(('dbscan', {"eps": eps, "min_samples": samples})
          for eps in (1.0, 1.5, 2.0, 2.5) for samples in (10, 20)),
        *(('hdbscan', {"min_cluster_size": size, "min_samples": samples})
          for size in (15, 25, 40) for samples in (5, 10)),
    ]
    by_intent: dict[str, Any] = {}
    for intent in sorted({str(row["teacher_intent"]) for row in rows}):
        fit = _intent_role(rows, intent, "fit")
        calibration = _intent_role(rows, intent, "calibration")
        if len(fit) < 40 or len(calibration) < 20:
            continue
        scaler = StandardScaler().fit(matrix(fit))
        fit_x = scaler.transform(matrix(fit))
        calibration_x = scaler.transform(matrix(calibration))
        evaluated = []
        for method, parameters in candidates:
            labels = _fit_labels(method, parameters, fit_x, KMeans, DBSCAN, HDBSCAN)
            centroids, radii = _centroid_contract(fit_x, labels, np)
            if not centroids:
                continue
            calibration_labels = _assign_centroids(calibration_x, centroids, radii, np)
            approved = _approved_clusters(calibration, calibration_labels)
            calibration_metrics = _selection_metrics(calibration, calibration_labels, approved)
            evaluated.append({
                "method": method,
                "parameters": parameters,
                "clusters": len(centroids),
                "fit_noise": int(sum(int(label) < 0 for label in labels)),
                "approved_clusters": sorted(approved),
                "calibration": calibration_metrics,
                "contract": {
                    "centroids": {str(key): value.tolist() for key, value in centroids.items()},
                    "radii": {str(key): float(value) for key, value in radii.items()},
                    "normalization": {
                        "mean": [float(value) for value in scaler.mean_],
                        "scale": [float(value) for value in scaler.scale_],
                    },
                },
            })
        eligible = [item for item in evaluated if item["approved_clusters"]]
        if not eligible:
            by_intent[intent] = {"champion": None, "candidates": evaluated}
            continue
        champion = max(
            eligible,
            key=lambda item: (
                item["calibration"]["selected"], item["calibration"]["precision"],
                item["calibration"]["wilson_lower_95"], -candidates.index((item["method"], item["parameters"])),
            ),
        )
        contract = champion["contract"]
        centroids = {int(key): np.asarray(value) for key, value in contract["centroids"].items()}
        radii = {int(key): float(value) for key, value in contract["radii"].items()}
        audit = {}
        for name, population in _audit_sets(rows).items():
            intent_rows = [row for row in population if row["teacher_intent"] == intent]
            labels = (
                _assign_centroids(scaler.transform(matrix(intent_rows)), centroids, radii, np)
                if intent_rows else []
            )
            audit[name] = _selection_metrics(intent_rows, labels, set(champion["approved_clusters"]))
        champion["audit"] = audit
        by_intent[intent] = {"champion": champion, "candidates": evaluated}

    payload = {
        "schema_version": "e2b-runtime-cluster-benchmark-v1",
        "rows": len(rows),
        "invalid_predictions_excluded": len(ledger) - len(rows),
        "feature_profile": args.feature_profile,
        "feature_names": list(feature_names),
        "selection_policy": "fit geometry; calibration approves clusters; protected sets audit only",
        "cluster_gate": "support>=20, precision>=0.90, Wilson lower 95%>=0.75",
        "by_intent": by_intent,
    }
    output = _absolute(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(_summary(payload), sort_keys=True))
    return 0


def _fit_labels(method: str, parameters: Mapping[str, Any], values: Any, kmeans: Any, dbscan: Any, hdbscan: Any) -> Any:
    if method == "kmeans":
        return kmeans(n_clusters=int(parameters["clusters"]), n_init=20, random_state=72).fit_predict(values)
    if method == "dbscan":
        return dbscan(eps=float(parameters["eps"]), min_samples=int(parameters["min_samples"])).fit_predict(values)
    return hdbscan(
        min_cluster_size=int(parameters["min_cluster_size"]),
        min_samples=int(parameters["min_samples"]),
        allow_single_cluster=False,
    ).fit_predict(values)


def _centroid_contract(values: Any, labels: Sequence[int], np: Any) -> tuple[dict[int, Any], dict[int, float]]:
    centroids, radii = {}, {}
    for label in sorted({int(value) for value in labels if int(value) >= 0}):
        members = values[np.asarray(labels) == label]
        centroid = members.mean(axis=0)
        distances = np.linalg.norm(members - centroid, axis=1)
        centroids[label] = centroid
        radii[label] = max(float(np.quantile(distances, 0.95)), 1e-9)
    return centroids, radii


def _assign_centroids(values: Any, centroids: Mapping[int, Any], radii: Mapping[int, float], np: Any) -> list[int]:
    assigned = []
    for value in values:
        distances = {label: float(np.linalg.norm(value - centroid)) for label, centroid in centroids.items()}
        label = min(distances, key=distances.get)
        assigned.append(label if distances[label] <= radii[label] else -1)
    return assigned


def _approved_clusters(rows: Sequence[Mapping[str, Any]], labels: Sequence[int]) -> set[int]:
    approved = set()
    for label in sorted({int(value) for value in labels if int(value) >= 0}):
        selected = [row for row, observed in zip(rows, labels, strict=True) if observed == label]
        correct = sum(int(row["target"]) for row in selected)
        if len(selected) >= 20 and correct / len(selected) >= 0.90 and _wilson(correct, len(selected)) >= 0.75:
            approved.add(label)
    return approved


def _selection_metrics(rows: Sequence[Mapping[str, Any]], labels: Sequence[int], approved: set[int]) -> dict[str, Any]:
    selected = [row for row, label in zip(rows, labels, strict=True) if label in approved]
    correct = sum(int(row["target"]) for row in selected)
    return {
        "population": len(rows), "selected": len(selected), "correct": correct,
        "coverage": len(selected) / len(rows) if rows else 0.0,
        "precision": correct / len(selected) if selected else 0.0,
        "wilson_lower_95": _wilson(correct, len(selected)),
    }


def _wilson(correct: int, total: int) -> float:
    if not total:
        return 0.0
    z = 1.959963984540054
    p = correct / total
    denominator = 1 + z * z / total
    return (p + z * z / (2 * total) - z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)) / denominator


def _intent_role(rows: Sequence[Mapping[str, Any]], intent: str, role: str) -> list[Mapping[str, Any]]:
    return [row for row in rows if row["teacher_intent"] == intent and row["role"] == role]


def _audit_sets(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    return {
        "boundary_external": [row for row in rows if row["source"] == "boundary"],
        "expansion_holdout": [row for row in rows if row["source"] == "expansion" and row["role"] == "protected_holdout"],
        "historical_holdout": [row for row in rows if row["source"] in {"legacy", "v2"} and row["role"] == "protected_holdout"],
        "all_protected": [row for row in rows if row["role"] in {"protected_holdout", "external_audit"}],
    }


def _summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = {}
    for intent, value in payload["by_intent"].items():
        champion = value["champion"]
        result[intent] = None if champion is None else {
            "method": champion["method"], "parameters": champion["parameters"],
            "calibration": champion["calibration"], "audit": champion["audit"],
        }
    return result


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
