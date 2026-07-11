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

from router.core.contracts import TaskEnvelope
from router.orchestration.final_validator import apply_answer_contract


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit conservative Answer Contract Engine transformations.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    result = audit(_absolute(args.candidates), _absolute(args.matrix))
    output = _absolute(args.output)
    report = _absolute(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report.write_text(_markdown(result), encoding="utf-8")
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


def audit(candidates_path: Path, matrix_path: Path) -> dict[str, Any]:
    candidates = {str(row["task_id"]): row for row in _jsonl(candidates_path)}
    matrix = {str(row["task_id"]): row for row in _jsonl(matrix_path)}
    if set(candidates) != set(matrix):
        raise ValueError("Candidate and matrix task IDs must match exactly.")
    summary: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    actions: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    review: list[dict[str, Any]] = []
    for task_id in sorted(matrix):
        row = matrix[task_id]
        candidate = candidates[task_id]
        application = apply_answer_contract(
            TaskEnvelope(id=task_id, input_text=str(candidate["task_text"])),
            str(candidate.get("answer") or ""),
        )
        summary["rows"] += 1
        summary["contract_valid"] += int(application.valid)
        summary["contract_invalid"] += int(not application.valid)
        summary["changed"] += int(application.changed)
        summary["original_format_invalid"] += int(row.get("format_valid") is False)
        recoverable = row.get("format_valid") is False and application.valid and application.changed
        summary["format_invalid_safely_transformed"] += int(recoverable)
        summary["correct_format_valid_changed"] += int(
            row.get("correct") is True and row.get("format_valid") is True and application.changed
        )
        kinds[application.contract.kind.value] += 1
        reasons[application.reason] += 1
        actions.update(application.actions)
        if application.changed:
            review.append(
                {
                    "task_id": task_id,
                    "contract": application.contract.kind.value,
                    "actions": list(application.actions),
                    "original_correct": row.get("correct"),
                    "original_format_valid": row.get("format_valid"),
                    "before_preview": str(candidate.get("answer") or "")[:240],
                    "after_preview": application.answer[:240],
                }
            )
    return {
        "schema_version": "answer-contract-audit-v1",
        "summary": dict(sorted(summary.items())),
        "contract_kinds": dict(sorted(kinds.items())),
        "actions": dict(sorted(actions.items())),
        "reasons": dict(sorted(reasons.items())),
        "changed_rows_for_review": review,
        "interpretation": (
            "format_invalid_safely_transformed is a mechanical recovery candidate count, not a new accuracy score; "
            "changed answers require frozen-set re-judging before promotion"
        ),
    }


def _markdown(result: Mapping[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Answer Contract Engine Audit",
        "",
        "This audit is deterministic and makes no semantic-accuracy claim.",
        "",
        "| Metric | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| `{key}` | {value} |" for key, value in summary.items())
    lines.extend(["", "## Transformations", "", "| Action | Count |", "|---|---:|"])
    lines.extend(f"| `{key}` | {value} |" for key, value in result["actions"].items())
    lines.extend(
        [
            "",
            "## Promotion Rule",
            "",
            "Re-judge every changed row and pass the frozen accuracy, output-contract, latency and memory gates before enabling a rule.",
            "",
        ]
    )
    return "\n".join(lines)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
