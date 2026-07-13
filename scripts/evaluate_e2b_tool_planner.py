#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from time import perf_counter
from urllib.request import Request, urlopen

from router.core.contracts import TaskEnvelope
from router.core.tool_planner import build_tool_planner_messages, parse_tool_plan, validate_tool_plan_provenance
from router.orchestration.tool_executor import run_tool_route


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=Path, default=Path("evals/tool-planner-v2/corpus.jsonl"))
    parser.add_argument("--base-url", default="http://127.0.0.1:9379/v1")
    parser.add_argument("--model", default="gemma4-e2b")
    parser.add_argument("--split", choices=("all", "development", "sealed"), default="all")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--per-family", type=int, default=0)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.tasks.read_text().splitlines() if line.strip()]
    if args.split != "all":
        rows = [row for row in rows if row.get("split") == args.split]
    if args.per_family:
        selected = []
        counts: dict[str, int] = defaultdict(int)
        for row in rows:
            family = row.get("family", row["expected"]["tool"])
            if counts[family] < args.per_family:
                selected.append(row)
                counts[family] += 1
        rows = selected
    if args.limit:
        rows = rows[:args.limit]
    results = []
    for row in rows:
        started = perf_counter()
        raw = _complete(args.base_url, args.model, row["prompt"], max_tokens=args.max_tokens)
        actual = None
        error = ""
        try:
            plan = validate_tool_plan_provenance(row["prompt"], parse_tool_plan(raw))
            actual = plan.to_dict()
        except ValueError as exc:
            error = str(exc)
        task = TaskEnvelope(id=row["id"], input_text=row["prompt"])
        decision = run_tool_route(task, raw)
        expected = row["expected"]
        expected_tool = expected["tool"]
        unsafe_false_positive = expected_tool == "none" and decision.accepted
        final_correct = bool(
            (expected_tool == "none" and not decision.accepted)
            or (decision.accepted and decision.answer == row.get("expected_answer"))
        )
        results.append({
            "id": row["id"], "family": row.get("family", expected_tool),
            "difficulty": row.get("difficulty", "unknown"), "split": row.get("split", "unknown"),
            "expected": expected, "expected_answer": row.get("expected_answer", ""),
            "actual": actual, "raw": raw, "schema_valid": actual is not None,
            "tool_correct": bool(actual and actual["tool"] == expected_tool),
            "exact_plan": actual == expected, "route": decision.to_dict(),
            "final_correct": final_correct, "unsafe_false_positive": unsafe_false_positive,
            "error": error, "latency_ms": round((perf_counter() - started) * 1000, 2),
        })
    summary = _summary(results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"summary": summary, "rows": results}, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0


def _summary(results: list[dict]) -> dict:
    families: dict[str, list[dict]] = defaultdict(list)
    for row in results:
        families[row["family"]].append(row)
    return {
        "tasks": len(results),
        "schema_valid": sum(row["schema_valid"] for row in results),
        "tool_correct": sum(row["tool_correct"] for row in results),
        "exact_plan": sum(row["exact_plan"] for row in results),
        "final_correct": sum(row["final_correct"] for row in results),
        "unsafe_false_positive": sum(row["unsafe_false_positive"] for row in results),
        "mean_latency_ms": round(sum(row["latency_ms"] for row in results) / max(1, len(results)), 2),
        "by_family": {
            family: {
                "tasks": len(rows),
                "final_correct": sum(row["final_correct"] for row in rows),
                "accepted": sum(row["route"]["accepted"] for row in rows),
                "unsafe_false_positive": sum(row["unsafe_false_positive"] for row in rows),
            }
            for family, rows in sorted(families.items())
        },
    }


def _complete(base_url: str, model: str, prompt: str, *, max_tokens: int) -> str:
    payload = json.dumps({
        "model": model,
        "messages": build_tool_planner_messages(prompt),
        "temperature": 0,
        "max_tokens": max_tokens,
    }).encode()
    request = Request(
        base_url.rstrip("/") + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urlopen(request, timeout=90) as response:
        body = json.load(response)
    return str(body["choices"][0]["message"]["content"])


if __name__ == "__main__":
    raise SystemExit(main())
