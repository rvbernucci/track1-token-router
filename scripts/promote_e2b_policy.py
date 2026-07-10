#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import Engine, FeatureVector
from router.orchestration.outcome_models import OutcomeModelBundle, OutcomeModelPredictor


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit locked-test evidence and forge an E2B route policy.")
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--base-policy", type=Path, required=True)
    parser.add_argument("--output-policy", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--accuracy-gate", type=float, default=0.60)
    parser.add_argument("--minimum-selected", type=int, default=30)
    args = parser.parse_args(argv)
    result = promote(
        matrix_path=args.matrix,
        models_path=args.models,
        base_policy_path=args.base_policy,
        output_policy_path=args.output_policy,
        report_path=args.report,
        accuracy_gate=args.accuracy_gate,
        minimum_selected=args.minimum_selected,
    )
    print(json.dumps(result["decision"], sort_keys=True))
    return 0


def promote(
    *,
    matrix_path: Path,
    models_path: Path,
    base_policy_path: Path,
    output_policy_path: Path,
    report_path: Path,
    accuracy_gate: float,
    minimum_selected: int,
) -> dict[str, Any]:
    if not 0 < accuracy_gate <= 1 or minimum_selected < 1:
        raise ValueError("Promotion thresholds are invalid.")
    rows = [
        row for row in _jsonl(matrix_path)
        if row.get("regression_split") == "test"
        and (row.get("model_id") or row.get("engine")) == "gemma4-e2b"
    ]
    if not rows:
        raise ValueError("Matrix has no locked-test E2B rows.")
    bundle = OutcomeModelBundle.load(models_path)
    predictor = OutcomeModelPredictor(bundle, allowed_models=[])
    selected: list[tuple[Mapping[str, Any], float, float]] = []
    scored: list[tuple[Mapping[str, Any], float, float]] = []
    for row in rows:
        features = FeatureVector.from_mapping(row["features"])
        prediction = predictor.predict(features, Engine.GEMMA_E2B)
        uncertainty = predictor.uncertainty(prediction)
        lower = max(0.0, prediction.probability_correct - uncertainty)
        item = (row, prediction.probability_correct, lower)
        scored.append(item)
        if lower >= accuracy_gate:
            selected.append(item)

    successes = sum(row.get("correct") is True for row, _, _ in selected)
    lower_test = _wilson_lower(successes, len(selected)) if selected else 0.0
    promoted = len(selected) >= minimum_selected and lower_test >= accuracy_gate
    intents = Counter(str(row["assessment"]["intent"]) for row, _, _ in selected)
    decision = {
        "promoted": promoted,
        "accuracy_gate": accuracy_gate,
        "minimum_selected": minimum_selected,
        "locked_test_rows": len(rows),
        "selected_rows": len(selected),
        "selected_coverage": len(selected) / len(rows),
        "selected_correct": successes,
        "selected_accuracy": successes / len(selected) if selected else 0.0,
        "selected_wilson_lower_95": lower_test,
        "selected_intents": dict(sorted(intents.items())),
        "disagreements_or_failures_counted_as_not_correct": sum(
            row.get("correct") is not True for row, _, _ in selected
        ),
    }
    policy = json.loads(base_policy_path.read_text(encoding="utf-8"))
    if not isinstance(policy, dict) or policy.get("schema_version") != "e2b-route-policy-v1":
        raise ValueError("Base E2B policy schema is invalid.")
    policy["default_enabled"] = promoted
    policy["approved_intents"] = sorted(intents) if promoted else []
    policy["decision_evidence"] = {
        **dict(policy.get("decision_evidence") or {}),
        "regression_matrix_rows": len(_jsonl(matrix_path)),
        "locked_test": decision,
        "outcome_model_artifact": str(models_path),
    }
    policy["reason"] = (
        "E2B passed the frozen locked-test Wilson gate; runtime still applies per-bin lower bounds."
        if promoted
        else "E2B did not pass the frozen locked-test Wilson gate and remains disabled."
    )
    output_policy_path.parent.mkdir(parents=True, exist_ok=True)
    output_policy_path.write_text(json.dumps(policy, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = {
        "schema_version": "e2b-promotion-report-v1",
        "decision": decision,
        "prediction_ranges": {
            "minimum": min(probability for _, probability, _ in scored),
            "maximum": max(probability for _, probability, _ in scored),
            "lower_bound_minimum": min(lower for _, _, lower in scored),
            "lower_bound_maximum": max(lower for _, _, lower in scored),
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _wilson_lower(successes: int, observations: int) -> float:
    if observations <= 0 or not 0 <= successes <= observations:
        return 0.0
    rate = successes / observations
    z = 1.959963984540054
    denominator = 1.0 + z * z / observations
    center = rate + z * z / (2.0 * observations)
    margin = z * math.sqrt(rate * (1.0 - rate) / observations + z * z / (4.0 * observations * observations))
    return max(0.0, (center - margin) / denominator)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
