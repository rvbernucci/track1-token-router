#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.orchestration.final_validator import apply_answer_contract
from scripts.evaluate_e2b_mechanical_holdout import score_answer


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score candidates before and after the Answer Contract Engine.")
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = evaluate(_absolute(args.tasks), _absolute(args.candidates))
    output = _absolute(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


def evaluate(tasks_path: Path, candidates_path: Path) -> dict[str, Any]:
    tasks = {str(row["id"]): row for row in _jsonl(tasks_path)}
    candidates = {str(row["task_id"]): row for row in _jsonl(candidates_path)}
    if set(tasks) != set(candidates):
        raise ValueError("Task and candidate IDs must match exactly.")
    counts: Counter[str] = Counter()
    actions: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for task_id in sorted(tasks):
        task_row = tasks[task_id]
        candidate = candidates[task_id]
        raw = str(candidate.get("answer") or "")
        application = apply_answer_contract(
            TaskEnvelope(id=task_id, input_text=str(task_row["input_text"])),
            raw,
        )
        final = application.answer if application.valid else raw.strip()
        raw_correct, raw_reason = score_answer(task_row["evaluation"], raw)
        final_correct, final_reason = score_answer(task_row["evaluation"], final)
        counts["rows"] += 1
        counts["raw_correct"] += int(raw_correct)
        counts["final_correct"] += int(final_correct)
        counts["contract_valid"] += int(application.valid)
        counts["contract_invalid"] += int(not application.valid)
        counts["changed"] += int(final != raw.strip())
        counts["recovered"] += int(not raw_correct and final_correct)
        counts["regressed"] += int(raw_correct and not final_correct)
        usage = candidate.get("fireworks_tokens") or {}
        counts["fireworks_tokens"] += int(usage.get("prompt") or 0) + int(usage.get("completion") or 0)
        actions.update(application.actions)
        rows.append(
            {
                "task_id": task_id,
                "raw_correct": raw_correct,
                "final_correct": final_correct,
                "raw_score_reason": raw_reason,
                "final_score_reason": final_reason,
                "contract": application.to_dict(),
            }
        )
    summary: dict[str, Any] = dict(sorted(counts.items()))
    summary["raw_accuracy"] = counts["raw_correct"] / counts["rows"]
    summary["final_accuracy"] = counts["final_correct"] / counts["rows"]
    summary["accuracy_delta"] = summary["final_accuracy"] - summary["raw_accuracy"]
    return {
        "schema_version": "answer-contract-candidate-eval-v1",
        "summary": summary,
        "actions": dict(sorted(actions.items())),
        "rows": rows,
    }


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
