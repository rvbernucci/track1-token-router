#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from router.core.contracts import TaskEnvelope
from router.core.tool_planner import validate_tool_plan_provenance
from router.functiongemma.tool_planner_provider import FunctionGemmaToolPlannerError, FunctionGemmaToolPlannerProvider
from router.orchestration.tool_executor import execute_tool_plan
from scripts.evaluate_functiongemma_tool_planner import _rows, _stratified, _summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a FunctionGemma planner through an OpenAI-compatible endpoint.")
    parser.add_argument("--data", type=Path, default=Path("data/functiongemma-tool-planner-v1"))
    parser.add_argument("--split", choices=("train", "validation", "calibration", "sealed"), required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--max-tokens", type=int, default=160)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = _rows(args.data / f"{args.split}.jsonl")
    if args.limit:
        rows = _stratified(rows, args.limit)
    provider = FunctionGemmaToolPlannerProvider(
        base_url=args.base_url,
        model=args.model,
        timeout_s=args.timeout,
        max_tokens=args.max_tokens,
    )
    predictions = []
    for row in rows:
        prediction = None
        error = ""
        accepted = False
        final_correct = False
        latency = 0.0
        try:
            invocation = provider.plan_with_trace(TaskEnvelope(id=row["id"], input_text=row["messages"][1]["content"]))
            latency = invocation.latency_ms
            plan = invocation.plan
            if plan.tool != "none":
                plan = validate_tool_plan_provenance(row["messages"][1]["content"], plan)
                evidence = execute_tool_plan(plan)
                accepted = True
                final_correct = evidence.result.replace(",", "") == row["expected_answer"].replace(",", "")
            else:
                final_correct = row["expected_function"] == "decline_tool"
            prediction = plan.to_dict()
        except (FunctionGemmaToolPlannerError, KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
            error = str(exc)
        predicted_function = "decline_tool" if prediction and prediction["tool"] == "none" else (prediction or {}).get("tool")
        arguments_exact = bool(prediction and (
            prediction.get("arguments") == row.get("expected_arguments")
            or (row["expected_function"] == "decline_tool" and prediction.get("tool") == "none")
        ))
        predictions.append({
            "id": row["id"], "family": row["family"], "split": row["split"],
            "expected_function": row["expected_function"], "predicted_function": predicted_function,
            "schema_valid": prediction is not None,
            "tool_correct": predicted_function == row["expected_function"],
            "arguments_exact": arguments_exact,
            "accepted": accepted, "final_correct": final_correct,
            "unsafe_false_positive": row["expected_function"] == "decline_tool" and accepted,
            "raw_output": "", "error": error, "latency_ms": round(latency, 2),
        })
    summary = _summary(predictions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"summary": summary, "rows": predictions}, indent=2) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
