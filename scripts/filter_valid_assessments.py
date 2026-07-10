#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskAssessment


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Filter fail-closed FunctionGemma assessments.")
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--assessments", type=Path, required=True)
    parser.add_argument("--valid-tasks", type=Path, required=True)
    parser.add_argument("--valid-assessments", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = filter_valid(
        tasks_path=args.tasks,
        assessments_path=args.assessments,
        valid_tasks_path=args.valid_tasks,
        valid_assessments_path=args.valid_assessments,
        report_path=args.report,
    )
    print(json.dumps(report, sort_keys=True))
    return 0


def filter_valid(
    *,
    tasks_path: Path,
    assessments_path: Path,
    valid_tasks_path: Path,
    valid_assessments_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    tasks = _jsonl(tasks_path)
    assessments = _jsonl(assessments_path)
    by_id: dict[str, Mapping[str, Any]] = {}
    for row in assessments:
        task_id = str(row.get("id") or "")
        if not task_id or task_id in by_id:
            raise ValueError("Assessment ids must be unique and non-empty.")
        by_id[task_id] = row
    task_ids = [str(row.get("id") or "") for row in tasks]
    if not all(task_ids) or len(set(task_ids)) != len(task_ids) or set(task_ids) != set(by_id):
        raise ValueError("Tasks and assessments must have identical unique ids.")

    valid_tasks: list[Mapping[str, Any]] = []
    valid_assessments: list[Mapping[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for task in tasks:
        task_id = str(task["id"])
        assessment = by_id[task_id]
        try:
            if assessment.get("parse_error") is not None:
                raise ValueError(str(assessment["parse_error"]))
            prediction = assessment.get("prediction")
            if not isinstance(prediction, Mapping):
                raise ValueError("missing prediction")
            TaskAssessment.from_mapping(prediction)
        except (TypeError, ValueError) as exc:
            excluded.append({"id": task_id, "reason": str(exc)[:500]})
            continue
        valid_tasks.append(task)
        valid_assessments.append(assessment)

    _write_jsonl(valid_tasks_path, valid_tasks)
    _write_jsonl(valid_assessments_path, valid_assessments)
    report = {
        "schema_version": "functiongemma-assessment-filter-v1",
        "total": len(tasks),
        "valid": len(valid_tasks),
        "excluded": len(excluded),
        "valid_split_counts": dict(sorted(Counter(str(row.get("regression_split")) for row in valid_tasks).items())),
        "exclusions": excluded,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
