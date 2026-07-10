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

from scripts.build_engine_outcome_matrix import _consensus, _judgment_index, _load_judge_policy


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select Fireworks models on validation and score locked test.")
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, action="append", required=True)
    parser.add_argument("--judgments", type=Path, action="append", required=True)
    parser.add_argument("--judge-policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args(argv)
    report = compare(
        tasks_path=args.tasks,
        candidate_paths=args.candidate,
        judgment_paths=args.judgments,
        judge_policy_path=args.judge_policy,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["locked_test_policy"], sort_keys=True))
    return 0


def compare(
    *,
    tasks_path: Path,
    candidate_paths: Sequence[Path],
    judgment_paths: Sequence[Path],
    judge_policy_path: Path,
) -> dict[str, Any]:
    tasks = {str(row["id"]): row for row in _jsonl(tasks_path)}
    policy = _load_judge_policy(judge_policy_path)
    judgments = _judgment_index(judgment_paths)
    observations: list[dict[str, Any]] = []
    for path in candidate_paths:
        for candidate in _jsonl(path):
            task = tasks[str(candidate["task_id"])]
            model = str(candidate["model_id"])
            correct, consensus, judges, _ = _consensus(
                judgments.get(str(candidate["id"]), []), allowed_judges=policy[model]
            ) if candidate.get("status") == "answered" else (None, "runtime_failure", [], None)
            usage = candidate.get("fireworks_tokens") or {}
            observations.append({
                "task_id": candidate["task_id"],
                "model": model,
                "split": task["regression_split"],
                "intent": task["source_assessment"]["intent"],
                "correct": correct,
                "consensus": consensus,
                "tokens": int(usage.get("prompt") or 0) + int(usage.get("completion") or 0),
            })
    models = sorted({row["model"] for row in observations})
    summary = {
        model: {
            split: _summarize([row for row in observations if row["model"] == model and row["split"] == split])
            for split in ("validation", "test")
        }
        for model in models
    }
    validation_choice: dict[str, str] = {}
    intents = sorted({row["intent"] for row in observations})
    intent_model_summary = {
        intent: {
            model: {
                split: _summarize(
                    [
                        row
                        for row in observations
                        if row["split"] == split and row["intent"] == intent and row["model"] == model
                    ]
                )
                for split in ("validation", "test")
            }
            for model in models
        }
        for intent in intents
    }
    for intent in intents:
        ranked = []
        for model in models:
            metrics = intent_model_summary[intent][model]["validation"]
            ranked.append((metrics["conservative_accuracy"], -metrics["average_tokens"], model))
        validation_choice[intent] = max(ranked)[2]
    selected_test = [
        row for row in observations
        if row["split"] == "test" and row["model"] == validation_choice[row["intent"]]
    ]
    return {
        "schema_version": "fireworks-baseline-comparison-v1",
        "model_summary": summary,
        "intent_model_summary": intent_model_summary,
        "selection_protocol": {
            "selection_split": "validation",
            "primary_metric": "conservative_accuracy",
            "tie_breaker": "lower_average_total_tokens",
            "locked_test_used_for_selection": False,
        },
        "validation_selected_model_by_intent": validation_choice,
        "locked_test_policy": _summarize(selected_test),
    }


def _summarize(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    correct = sum(row.get("correct") is True for row in rows)
    binary = [row for row in rows if isinstance(row.get("correct"), bool)]
    return {
        "rows": total,
        "correct": correct,
        "incorrect_or_uncertain": total - correct,
        "conservative_accuracy": correct / total if total else 0.0,
        "binary_accuracy": sum(row["correct"] is True for row in binary) / len(binary) if binary else 0.0,
        "binary_rows": len(binary),
        "conservative_wilson_lower_95": _wilson_lower(correct, total),
        "binary_wilson_lower_95": _wilson_lower(sum(row["correct"] is True for row in binary), len(binary)),
        "tokens": sum(int(row["tokens"]) for row in rows),
        "average_tokens": sum(int(row["tokens"]) for row in rows) / total if total else 0.0,
    }


def _wilson_lower(successes: int, total: int, *, z: float = 1.959963984540054) -> float:
    if total <= 0:
        return 0.0
    proportion = successes / total
    denominator = 1.0 + (z * z / total)
    centre = proportion + (z * z / (2.0 * total))
    margin = z * math.sqrt((proportion * (1.0 - proportion) / total) + (z * z / (4.0 * total * total)))
    return (centre - margin) / denominator


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Fireworks Locked-Test Baseline",
        "",
        "Models are selected per intent using validation only. Judge disagreement is counted as not correct in conservative accuracy.",
        "",
        "| Model | Split | Rows | Conservative accuracy | Binary accuracy | Total tokens | Avg tokens |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for model, splits in sorted(report["model_summary"].items()):
        for split, metrics in sorted(splits.items()):
            lines.append(
                f"| `{model}` | {split} | {metrics['rows']} | {metrics['conservative_accuracy']:.3f} | "
                f"{metrics['binary_accuracy']:.3f} | {metrics['tokens']} | {metrics['average_tokens']:.1f} |"
            )
    policy = report["locked_test_policy"]
    intent_summary = report.get("intent_model_summary") or {}
    lines.extend([
        "",
        "## Validation-Selected Policy",
        "",
        *[f"- `{intent}`: `{model}`" for intent, model in sorted(report["validation_selected_model_by_intent"].items())],
        "",
        "The choices above were frozen before locked-test disclosure. Wilson bounds are reported for uncertainty, not used for post-test reselection.",
        "",
        "| Intent | Model | Validation accuracy | Wilson lower 95% | Avg tokens |",
        "| --- | --- | ---: | ---: | ---: |",
        *[
            f"| `{intent}` | `{model}` | {metrics['validation']['conservative_accuracy']:.3f} | "
            f"{metrics['validation']['conservative_wilson_lower_95']:.3f} | {metrics['validation']['average_tokens']:.1f} |"
            for intent, models in sorted(intent_summary.items())
            for model, metrics in sorted(models.items())
        ],
        "",
        f"Locked-test conservative accuracy: `{policy['conservative_accuracy']:.3f}`  ",
        f"Locked-test Fireworks tokens: `{policy['tokens']}`  ",
        f"Average tokens per task: `{policy['average_tokens']:.1f}`",
        "",
    ])
    return "\n".join(lines)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
