#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
from threading import Lock
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.core.tool_planner import validate_tool_plan_provenance
from router.functiongemma.tool_planner_provider import (
    FunctionGemmaToolPlannerError,
    FunctionGemmaToolPlannerProvider,
)
from router.orchestration.tool_executor import execute_tool_plan, verify_tool_evidence


SCHEMA_VERSION = "amd-tool-planner-population-v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay FunctionGemma planner train and validation populations.")
    parser.add_argument("--data", type=Path, default=Path("data/functiongemma-tool-planner-v1"))
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.workers < 1 or args.timeout <= 0:
        parser.error("workers and timeout must be positive")

    rows = _rows(args.data / "train.jsonl") + _rows(args.data / "validation.jsonl")
    if len(rows) != 2000 or len({row["id"] for row in rows}) != 2000:
        raise ValueError(f"Expected 2,000 unique planner rows, found {len(rows)}")
    completed = _completed_ids(args.output) if args.resume else set()
    if args.output.exists() and not args.resume:
        raise ValueError("Output exists; pass --resume to append only missing tasks.")
    pending = [row for row in rows if row["id"] not in completed]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    provider = FunctionGemmaToolPlannerProvider(
        base_url=args.base_url,
        model=args.model,
        timeout_s=args.timeout,
        max_tokens=160,
    )
    lock = Lock()
    written = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_run, provider, row): row["id"] for row in pending}
        for future in as_completed(futures):
            record = future.result()
            with lock, args.output.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            written += 1
            if written % 100 == 0:
                print(json.dumps({"written": written, "remaining": len(pending) - written}), flush=True)

    print(json.dumps({"population": len(rows), "resumed": len(completed), "written": written}, sort_keys=True))
    return 0


def _run(provider: FunctionGemmaToolPlannerProvider, row: dict[str, Any]) -> dict[str, Any]:
    prompt = str(row["messages"][1]["content"])
    expected_function = str(row["expected_function"])
    expected_answer = str(row.get("expected_answer") or "")
    try:
        invocation = provider.plan_with_trace(TaskEnvelope(id=str(row["id"]), input_text=prompt))
        plan = invocation.plan
        accepted = False
        evidence = None
        answer = ""
        if plan.tool != "none":
            plan = validate_tool_plan_provenance(prompt, plan)
            evidence = execute_tool_plan(plan)
            if not verify_tool_evidence(evidence):
                raise ValueError("Tool evidence failed independent verification.")
            accepted = True
            answer = evidence.result
        predicted_function = "decline_tool" if plan.tool == "none" else plan.tool
        final_correct = (
            (expected_function == "decline_tool" and not accepted)
            or (
                expected_function != "decline_tool"
                and accepted
                and answer.replace(",", "") == expected_answer.replace(",", "")
            )
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "id": row["id"],
            "family": row["family"],
            "split": row["split"],
            "prompt": prompt,
            "expected_function": expected_function,
            "expected_answer": expected_answer,
            "predicted_function": predicted_function,
            "plan": plan.to_dict(),
            "accepted": accepted,
            "answer": answer,
            "evidence": evidence.to_dict() if evidence else None,
            "tool_correct": predicted_function == expected_function,
            "final_correct": final_correct,
            "unsafe_false_positive": expected_function == "decline_tool" and accepted,
            "latency_ms": round(invocation.latency_ms, 2),
            "error": None,
        }
    except (FunctionGemmaToolPlannerError, KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "id": row["id"],
            "family": row["family"],
            "split": row["split"],
            "prompt": prompt,
            "expected_function": expected_function,
            "expected_answer": expected_answer,
            "predicted_function": None,
            "plan": None,
            "accepted": False,
            "answer": "",
            "evidence": None,
            "tool_correct": False,
            "final_correct": expected_function == "decline_tool",
            "unsafe_false_positive": False,
            "latency_ms": None,
            "error": f"{type(exc).__name__}:{exc}",
        }


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _completed_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        str(row["id"])
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in (json.loads(line),)
    }


if __name__ == "__main__":
    raise SystemExit(main())
