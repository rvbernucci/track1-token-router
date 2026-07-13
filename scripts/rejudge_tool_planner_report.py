#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

from router.core.contracts import TaskEnvelope
from router.core.tool_planner import parse_tool_plan, validate_tool_plan_provenance
from router.orchestration.tool_executor import run_tool_route


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, default=Path("evals/tool-planner-v2/corpus.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.input.read_text())
    tasks = {row["id"]: row for row in map(json.loads, args.tasks.read_text().splitlines()) if row}
    rows = []
    for old in report["rows"]:
        source = tasks[old["id"]]
        raw = old["raw"]
        actual = None
        error = ""
        try:
            actual = validate_tool_plan_provenance(source["prompt"], parse_tool_plan(raw)).to_dict()
        except ValueError as exc:
            error = str(exc)
        decision = run_tool_route(TaskEnvelope(id=source["id"], input_text=source["prompt"]), raw)
        expected_tool = source["expected"]["tool"]
        final_correct = (
            (expected_tool == "none" and not decision.accepted)
            or (decision.accepted and decision.answer == source["expected_answer"])
        )
        rows.append({
            **old, "expected": source["expected"], "expected_answer": source["expected_answer"],
            "actual": actual, "schema_valid": actual is not None,
            "tool_correct": bool(actual and actual["tool"] == expected_tool),
            "exact_plan": actual == source["expected"], "route": decision.to_dict(),
            "final_correct": final_correct,
            "unsafe_false_positive": expected_tool == "none" and decision.accepted,
            "error": error,
        })
    summary = _summary(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0


def _summary(rows: list[dict]) -> dict:
    families: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        families[row["family"]].append(row)
    return {
        "tasks": len(rows), "schema_valid": sum(row["schema_valid"] for row in rows),
        "tool_correct": sum(row["tool_correct"] for row in rows),
        "exact_plan": sum(row["exact_plan"] for row in rows),
        "final_correct": sum(row["final_correct"] for row in rows),
        "unsafe_false_positive": sum(row["unsafe_false_positive"] for row in rows),
        "mean_latency_ms": round(sum(row["latency_ms"] for row in rows) / max(1, len(rows)), 2),
        "by_family": {
            family: {
                "tasks": len(items), "final_correct": sum(row["final_correct"] for row in items),
                "accepted": sum(row["route"]["accepted"] for row in items),
                "unsafe_false_positive": sum(row["unsafe_false_positive"] for row in items),
            }
            for family, items in sorted(families.items())
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
