#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRIOR_SOURCES = (
    Path("data/e2b-regression-2000/tasks.jsonl"),
    Path("evals/e2b-regression-v2/inputs/train.jsonl"),
    Path("evals/e2b-regression-v2/inputs/validation.jsonl"),
    Path("evals/e2b-regression-v2/inputs/final_holdout.jsonl"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze sealed E2B boundary evidence without refitting.")
    parser.add_argument("--tasks", type=Path, default=Path("evals/e2b-boundary-v1/sealed/tasks.jsonl"))
    parser.add_argument("--predictions", type=Path, default=Path("reports/generated/e2b-boundary-v1/predictions.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("reports/generated/e2b-boundary-v1/detailed-analysis.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/public/e2b-boundary-detailed-analysis.md"))
    parser.add_argument("--threshold", type=float, default=.75)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = analyze(ROOT / args.tasks, ROOT / args.predictions, args.threshold)
    _write(ROOT / args.output, json.dumps(result, indent=2, sort_keys=True) + "\n")
    _write(ROOT / args.report, markdown(result))
    print(json.dumps(result, sort_keys=True))
    return 0 if not args.check or result["checks"]["zero_normalized_overlap"] else 1


def analyze(tasks_path: Path, predictions_path: Path, threshold: float) -> dict:
    tasks = {row["task_id"]: row for row in _jsonl(tasks_path)}
    predictions = _jsonl(predictions_path)
    prior = _prior_prompt_hashes()
    overlaps = [row["task_id"] for row in tasks.values() if _normalized_hash(row["prompt"]) in prior]
    selected = [row for row in predictions if row.get("assessment") and row.get("probability", 0) >= threshold]
    dimensions = {
        "intent": lambda row, task: row["assessment"]["raw_assessment"]["intent"],
        "output_shape": lambda row, task: task["output_shape"],
        "language": lambda row, task: task["language"],
        "prompt_length": lambda row, task: _length_band(len(task["prompt"])),
    }
    breakdown = {}
    for name, getter in dimensions.items():
        groups = defaultdict(list)
        for row in selected:
            groups[getter(row, tasks[row["task_id"]])].append(row)
        breakdown[name] = {key: _cohort(value) for key, value in sorted(groups.items())}
    counterexamples = sorted(
        (
            {
                "task_id": row["task_id"],
                "intent": row["assessment"]["raw_assessment"]["intent"],
                "probability": row["probability"],
                "prompt_chars": len(tasks[row["task_id"]]["prompt"]),
                "answer_sha256": hashlib.sha256(row["answer"].encode()).hexdigest(),
            }
            for row in selected if not row["correct"]
        ),
        key=lambda row: (row["prompt_chars"], -row["probability"]),
    )[:20]
    return {
        "schema_version": "e2b-boundary-detailed-analysis-v1",
        "threshold": threshold,
        "prior_rows_scanned": sum(_count(ROOT / path) for path in PRIOR_SOURCES),
        "normalized_overlap_count": len(overlaps),
        "normalized_overlap_task_ids": overlaps,
        "selected": len(selected),
        "breakdown": breakdown,
        "smallest_false_positive_counterexamples": counterexamples,
        "checks": {
            "all_predictions_have_tasks": all(row["task_id"] in tasks for row in predictions),
            "zero_normalized_overlap": not overlaps,
        },
    }


def _cohort(rows: list[dict]) -> dict:
    correct = sum(bool(row["correct"]) for row in rows)
    return {
        "selected": len(rows),
        "correct": correct,
        "false_positives": len(rows) - correct,
        "precision": correct / len(rows) if rows else None,
        "false_positive_rate": (len(rows) - correct) / len(rows) if rows else None,
    }


def _prior_prompt_hashes() -> set[str]:
    hashes = set()
    for relative in PRIOR_SOURCES:
        for row in _jsonl(ROOT / relative):
            prompt = row.get("prompt") or row.get("input_text")
            if isinstance(prompt, str):
                hashes.add(_normalized_hash(prompt))
    return hashes


def _normalized_hash(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"\s+", " ", value).strip()
    return hashlib.sha256(value.encode()).hexdigest()


def _length_band(length: int) -> str:
    if length < 160:
        return "short_lt_160"
    if length < 500:
        return "medium_160_499"
    return "long_gte_500"


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _count(path: Path) -> int:
    return len(_jsonl(path))


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def markdown(result: dict) -> str:
    lines = [
        "# E2B Boundary Detailed Analysis",
        "",
        f"- Prior rows scanned: `{result['prior_rows_scanned']}`",
        f"- Normalized overlaps: `{result['normalized_overlap_count']}`",
        f"- Selected rows: `{result['selected']}`",
        "",
        "## False-Positive Breakdown",
        "",
    ]
    for dimension, groups in result["breakdown"].items():
        lines.append(f"### {dimension.replace('_', ' ').title()}")
        lines.append("")
        for key, cohort in groups.items():
            lines.append(
                f"- `{key}`: selected `{cohort['selected']}`, false positives "
                f"`{cohort['false_positives']}`, precision `{cohort['precision']:.2%}`"
            )
        lines.append("")
    lines.extend(["## Smallest False Positives", ""])
    if not result["smallest_false_positive_counterexamples"]:
        lines.append("No false positives crossed the threshold.")
    else:
        for row in result["smallest_false_positive_counterexamples"]:
            lines.append(
                f"- `{row['task_id']}`: intent `{row['intent']}`, probability "
                f"`{row['probability']:.4f}`, prompt chars `{row['prompt_chars']}`"
            )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
