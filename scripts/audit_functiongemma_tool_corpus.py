#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from router.core.contracts import TaskEnvelope
from router.core.tool_planner import ToolPlan, validate_tool_plan_provenance
from router.orchestration.final_validator import apply_answer_contract
from router.orchestration.tool_executor import execute_tool_plan, verify_tool_evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/functiongemma-tool-planner-v1"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    split_ids: dict[str, set[str]] = {}
    errors = []
    tool_hashes = set()
    for split in ("train", "validation", "calibration", "sealed"):
        current = [json.loads(line) for line in (args.data / f"{split}.jsonl").read_text().splitlines() if line.strip()]
        split_ids[split] = {row["lineage"] for row in current}
        for row in current:
            try:
                _validate_row(row, split)
                tool_hashes.add(_canonical_hash(row["tools"]))
            except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
                errors.append({"id": row.get("id"), "split": split, "error": str(exc)})
        rows.extend(current)
    overlaps = {
        f"{left}:{right}": len(split_ids[left] & split_ids[right])
        for index, left in enumerate(split_ids)
        for right in list(split_ids)[index + 1:]
    }
    summary = {
        "schema_version": "functiongemma-tool-corpus-audit-v1",
        "rows": len(rows), "unique_ids": len({row["id"] for row in rows}),
        "unique_lineages": len({row["lineage"] for row in rows}),
        "errors": len(errors), "tool_schema_variants": len(tool_hashes),
        "split_overlaps": overlaps,
        "families": {family: sum(row["family"] == family for row in rows) for family in sorted({row["family"] for row in rows})},
        "unsupported": sum(row["expected_function"] == "decline_tool" for row in rows),
        "supported_proofs": sum(row["expected_function"] != "decline_tool" for row in rows),
    }
    passed = (
        summary["rows"] == 2500 and summary["unique_ids"] == 2500
        and summary["unique_lineages"] == 2500 and not errors
        and summary["tool_schema_variants"] == 1 and not any(overlaps.values())
    )
    payload = {"passed": passed, "summary": summary, "errors": errors}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": passed, **summary}, sort_keys=True))
    return 0 if passed else 2


def _validate_row(row: dict, split: str) -> None:
    required = {
        "id", "lineage", "family", "difficulty", "split", "messages", "tools",
        "expected_function", "expected_arguments", "expected_plan", "expected_answer",
        "source", "generator_version",
    }
    if set(row) != required or row["split"] != split:
        raise ValueError("Row fields or split are invalid.")
    messages = row["messages"]
    if not isinstance(messages, list) or len(messages) != 3 or [item.get("role") for item in messages] != ["developer", "user", "assistant"]:
        raise ValueError("Conversation shape is invalid.")
    calls = messages[2].get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1:
        raise ValueError("Exactly one native tool call is required.")
    function = calls[0].get("function", {})
    if function.get("name") != row["expected_function"] or function.get("arguments") != row["expected_arguments"]:
        raise ValueError("Native target differs from expected function.")
    if row["expected_function"] == "decline_tool":
        if row["expected_plan"] is not None or row["expected_answer"]:
            raise ValueError("Decline rows cannot contain executable outputs.")
        return
    plan = ToolPlan(row["expected_function"], row["expected_arguments"], "high")
    validate_tool_plan_provenance(messages[1]["content"], plan)
    evidence = execute_tool_plan(plan)
    if not verify_tool_evidence(evidence):
        raise ValueError("Expected proof is not recomputable.")
    contract = apply_answer_contract(TaskEnvelope(id=row["id"], input_text=messages[1]["content"]), evidence.result)
    if not contract.valid or contract.answer != row["expected_answer"]:
        raise ValueError("Expected answer violates the answer contract.")


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
