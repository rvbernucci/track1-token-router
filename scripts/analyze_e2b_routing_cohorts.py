#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SCENARIOS = {
    "balanced": {
        "factual_qa": 0.125,
        "math_reasoning": 0.125,
        "sentiment": 0.125,
        "summarization": 0.125,
        "ner": 0.125,
        "code_debugging": 0.125,
        "logic_puzzle": 0.125,
        "code_generation": 0.125,
    },
    "sentiment_heavy": {
        "sentiment": 0.70,
        "ner": 0.15,
        "factual_qa": 0.025,
        "math_reasoning": 0.025,
        "summarization": 0.025,
        "code_debugging": 0.025,
        "logic_puzzle": 0.025,
        "code_generation": 0.025,
    },
    "extraction_classification": {
        "sentiment": 0.45,
        "ner": 0.45,
        "factual_qa": 0.02,
        "math_reasoning": 0.02,
        "summarization": 0.02,
        "code_debugging": 0.02,
        "logic_puzzle": 0.01,
        "code_generation": 0.01,
    },
    "code_reasoning_heavy": {
        "code_generation": 0.30,
        "code_debugging": 0.20,
        "math_reasoning": 0.20,
        "logic_puzzle": 0.15,
        "factual_qa": 0.05,
        "sentiment": 0.04,
        "ner": 0.04,
        "summarization": 0.02,
    },
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze E2B local-routing cohorts and input-mix scenarios.")
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--policy-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    result = analyze(_absolute(args.matrix), _absolute(args.policy_report))
    _write_json(_absolute(args.output), result)
    report = _absolute(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(_markdown(result), encoding="utf-8")
    print(json.dumps(result["scenarios"], sort_keys=True))
    return 0


def analyze(matrix_path: Path, policy_report_path: Path) -> dict[str, Any]:
    matrix = _jsonl(matrix_path)
    policy = json.loads(policy_report_path.read_text(encoding="utf-8"))
    locked = policy["locked_diagnostic"]
    totals = Counter(
        str(row["assessment"]["intent"])
        for row in matrix
        if row.get("regression_split") == "test"
    )
    cohorts: dict[str, dict[str, float | int | None]] = {}
    for category, total in sorted(totals.items()):
        selected = locked["selected_by_intent"].get(category, {})
        selected_rows = int(selected.get("selected", 0))
        correct = int(selected.get("e2b_correct", 0))
        cohorts[category] = {
            "test_rows": total,
            "selected_rows": selected_rows,
            "correct_rows": correct,
            "coverage": selected_rows / total if total else 0.0,
            "precision": correct / selected_rows if selected_rows else None,
        }
    average_saved_tokens = float(locked["saved_fireworks_tokens"]) / max(1, int(locked["selected_rows"]))
    scenarios = {
        name: _scenario_metrics(weights, cohorts, average_saved_tokens)
        for name, weights in SCENARIOS.items()
    }
    observed_weights = {category: count / sum(totals.values()) for category, count in totals.items()}
    scenarios["observed_locked_mix"] = _scenario_metrics(observed_weights, cohorts, average_saved_tokens)
    return {
        "schema_version": "e2b-routing-cohorts-v1",
        "thresholds": {
            "pre_probability": locked["pre_threshold"],
            "post_probability": locked["post_threshold"],
        },
        "average_fireworks_tokens_saved_per_local_answer": average_saved_tokens,
        "cohorts": cohorts,
        "scenarios": scenarios,
        "operational_note": (
            "Coverage is distribution-dependent. Factual QA is unstable across splits and should remain remote "
            "until a fresh holdout confirms its local precision."
        ),
    }


def _scenario_metrics(
    weights: Mapping[str, float],
    cohorts: Mapping[str, Mapping[str, float | int | None]],
    average_saved_tokens: float,
) -> dict[str, float]:
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("Scenario weights must sum to one.")
    coverage = sum(float(weight) * float(cohorts[category]["coverage"]) for category, weight in weights.items())
    correct_local = sum(
        float(weight)
        * float(cohorts[category]["coverage"])
        * float(cohorts[category]["precision"] or 0.0)
        for category, weight in weights.items()
    )
    return {
        "expected_local_coverage": coverage,
        "expected_local_precision": correct_local / coverage if coverage else 0.0,
        "expected_local_answers_per_100": coverage * 100,
        "expected_fireworks_tokens_saved_per_100": coverage * 100 * average_saved_tokens,
    }


def _markdown(result: Mapping[str, Any]) -> str:
    lines = [
        "# E2B Routing Cohorts",
        "",
        "Coverage depends on the hidden input distribution; it is not a fixed global percentage.",
        "",
        "## Locked Cohorts",
        "",
        "| Category | Selected | Test rows | Coverage | Precision |",
        "|---|---:|---:|---:|---:|",
    ]
    for category, row in result["cohorts"].items():
        precision = "n/a" if row["precision"] is None else f"{float(row['precision']):.1%}"
        lines.append(
            f"| {category} | {row['selected_rows']} | {row['test_rows']} | "
            f"{float(row['coverage']):.1%} | {precision} |"
        )
    lines.extend(
        [
            "",
            "## Input-Mix Scenarios",
            "",
            "| Scenario | Local coverage | Local precision | Local / 100 | Saved tokens / 100 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for name, row in result["scenarios"].items():
        lines.append(
            f"| {name} | {float(row['expected_local_coverage']):.1%} | "
            f"{float(row['expected_local_precision']):.1%} | "
            f"{float(row['expected_local_answers_per_100']):.1f} | "
            f"{float(row['expected_fireworks_tokens_saved_per_100']):.0f} |"
        )
    lines.extend(["", str(result["operational_note"]), ""])
    return "\n".join(lines)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
