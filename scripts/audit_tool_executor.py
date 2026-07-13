#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from router.core.contracts import TaskEnvelope
from router.orchestration.tool_executor import run_tool_route, verify_tool_evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=Path, default=Path("evals/tool-planner-v2/corpus.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.tasks.read_text().splitlines() if line.strip()]
    results = []
    for row in rows:
        raw = json.dumps(row["expected"], separators=(",", ":"))
        decision = run_tool_route(TaskEnvelope(id=row["id"], input_text=row["prompt"]), raw)
        expected_none = row["expected"]["tool"] == "none"
        passed = (
            (expected_none and not decision.accepted)
            or (
                not expected_none and decision.accepted
                and decision.answer == row["expected_answer"]
                and decision.evidence is not None
                and verify_tool_evidence(decision.evidence)
            )
        )
        results.append({
            "id": row["id"], "family": row["family"], "split": row["split"],
            "passed": passed, "accepted": decision.accepted, "reason": decision.reason,
        })
    summary = {
        "schema_version": "tool-executor-audit-v1",
        "tasks": len(results), "passed": sum(row["passed"] for row in results),
        "failed": sum(not row["passed"] for row in results),
        "unsupported_accepted": sum(row["family"] == "none" and row["accepted"] for row in results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"summary": summary, "rows": results}, indent=2) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
