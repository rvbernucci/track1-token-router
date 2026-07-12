#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from router.orchestration.risk_ladder import RiskLadderPolicy, wilson_lower


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay E2B risk policies on frozen production evidence.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    ledger = {str(row["task_id"]): row for row in _rows(ROOT / "reports/generated/e2b-expansion-v1/regression-ledger.jsonl")}
    predictions = _rows(_absolute(args.predictions))
    matrix = json.loads((ROOT / "configs/e2b-category-matrix-regression-v2.json").read_text())
    ladder = RiskLadderPolicy.load(ROOT / "configs/wilson-nash-risk-ladder-v1.json")
    rows = []
    for prediction in predictions:
        row = ledger[str(prediction["id"])]
        assessment = prediction["prediction"]
        probability = _matrix_probability(matrix, assessment, row["mechanical_features"])
        rows.append({**row, "predicted_intent": assessment["intent"], "probability": probability})
    distributions = {
        "balanced": [row for row in rows if row["role"] in {"protected_holdout", "external_audit"}],
        "sentiment_heavy": [row for row in rows if row["category"] == "sentiment" and row["role"] in {"protected_holdout", "external_audit"}],
        "code_heavy": [row for row in rows if row["category"] in {"code_debugging", "code_generation"} and row["role"] in {"protected_holdout", "external_audit"}],
        "math_heavy": [row for row in rows if row["category"] == "math_reasoning" and row["role"] in {"protected_holdout", "external_audit"}],
        "random_500": sorted(rows, key=lambda row: hashlib.sha256(str(row["task_id"]).encode()).digest())[:500],
    }

    def current(row: Mapping[str, Any]) -> str:
        intent = str(row["predicted_intent"])
        return "e2b" if intent in matrix["allowed_intents"] and row["probability"] >= matrix["thresholds_by_intent"][intent] else "fireworks"

    def hard_95(row: Mapping[str, Any]) -> str:
        intent = str(row["predicted_intent"])
        evidence = ladder.evidence_by_intent.get(intent)
        eligible = row["probability"] >= ladder.eligibility_threshold_by_intent.get(intent, 1.0)
        return "e2b" if evidence and eligible and wilson_lower(*evidence, confidence=0.95) >= 0.75 else "fireworks"

    policies = {
        "current_v2_hard_gate": current,
        "wilson95_hard_gate": hard_95,
        "wilson90_nash_ladder": lambda row: ladder.decide(
            intent=str(row["predicted_intent"]), probability=float(row["probability"]), remaining_ms=60000,
        ).action,
        "raw_probability_070": lambda row: "e2b" if row["predicted_intent"] == "sentiment" and row["probability"] >= 0.70 else "fireworks",
    }
    result = {
        "schema_version": "wilson-nash-ablation-v1",
        "rows": len(rows),
        "fireworks_token_estimate_per_direct_answer": 128,
        "distributions": {
            name: {policy: _metrics(population, selector) for policy, selector in policies.items()}
            for name, population in distributions.items()
        },
    }
    output = _absolute(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["distributions"], sort_keys=True))
    return 0


def _matrix_probability(matrix: Mapping[str, Any], assessment: Mapping[str, Any], mechanical: Mapping[str, Any]) -> float:
    intent, scores = str(assessment["intent"]), assessment["scores"]
    if intent not in matrix["models_by_intent"]:
        return 0.0
    values = [float(scores[name]) / 10.0 for name in matrix["score_feature_names"]]
    values.extend(float(mechanical[name]) for name in matrix["mechanical_feature_names"])
    normalization = matrix["normalization_by_intent"][intent]
    values = [(value - mean) / scale for value, mean, scale in zip(values, normalization["mean"], normalization["scale"], strict=True)]
    coefficients = matrix["models_by_intent"][intent]
    probability = _sigmoid(coefficients[0] + sum(weight * value for weight, value in zip(coefficients[1:], values, strict=True)))
    calibrator = matrix["calibrators_by_intent"][intent]
    bounded = min(1 - 1e-6, max(1e-6, probability))
    return _sigmoid(calibrator[0] + calibrator[1] * math.log(bounded / (1 - bounded)))


def _metrics(rows: Sequence[Mapping[str, Any]], selector: Any) -> dict[str, Any]:
    actions = [selector(row) for row in rows]
    local = [row for row, action in zip(rows, actions, strict=True) if action == "e2b"]
    review = sum(action == "verify_or_repair" for action in actions)
    correct = sum(int(row["target"]) for row in local)
    remote = len(rows) - len(local)
    return {
        "population": len(rows), "local": len(local), "local_correct": correct,
        "false_local": len(local) - correct,
        "local_precision": correct / len(local) if local else 0.0,
        "review": review, "direct_fireworks": remote - review,
        "estimated_fireworks_tokens": (remote - review) * 128 + review * 96,
    }


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, value))))


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
