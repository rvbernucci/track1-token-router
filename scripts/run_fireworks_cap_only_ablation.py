#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
import os
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.fireworks import FireworksClient
from router.core.model_client import ModelClientError
from scripts.fireworks_microbench import _load_env_files
from scripts.run_fireworks_champion_v3 import AtomicLedger, Budget, MODELS

OUT = ROOT / "reports/generated/fireworks-cap-only-ablation"
KIMI, MINIMAX = MODELS


def rows(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def build_tasks() -> list[dict]:
    result = []
    for source, baseline_correct in (
        (ROOT / "reports/generated/fireworks-champion-v3-ablation/tasks.jsonl", False),
        (ROOT / "reports/generated/fireworks-champion-v3-preservation/tasks.jsonl", True),
    ):
        result.extend({**row, "current_frozen_correct": baseline_correct} for row in rows(source))
    deduplicated = {row["task_id"]: row for row in result}
    if len(result) != 160 or len(deduplicated) != 159:
        raise ValueError("cap-only ablation requires the frozen 160-row paired cohort")
    return list(deduplicated.values())


def cap(task: dict) -> int:
    category = task["category"]
    if category in {"code_debugging", "code_generation"}:
        return 512
    if category == "ner":
        return 384
    if category == "logic_puzzle":
        return 384
    if category == "math_reasoning":
        return 192
    return int(task.get("max_tokens") or 256)


def call(task: dict, key: str, base: str) -> dict:
    client = FireworksClient(base_url=base, model=task["model"], api_key=key, timeout_s=120, max_retries=1)
    started = perf_counter()
    try:
        response = client.complete(
            [{"role": "user", "content": task["prompt"]}],
            temperature=0, max_tokens=cap(task),
            extra_body={"reasoning_effort": "none", "user": "proofroute-cap-only-v1"},
        )
        return {
            "task_id": task["task_id"], "model": task["model"], "answer": response.text,
            "ok": bool(response.text.strip()), "usage": response.usage.to_dict(),
            "finish_reason": response.raw.get("choices", [{}])[0].get("finish_reason"),
            "max_tokens": cap(task), "latency_ms": round((perf_counter() - started) * 1000, 2),
            "protocol": "raw-prompt-cap-only-v1",
        }
    except ModelClientError as exc:
        return {
            "task_id": task["task_id"], "model": task["model"], "answer": "", "ok": False,
            "usage": {"prompt": 0, "completion": 0, "total": 0}, "finish_reason": None,
            "max_tokens": cap(task), "latency_ms": round((perf_counter() - started) * 1000, 2),
            "protocol": "raw-prompt-cap-only-v1", "error": str(exc)[:500],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--available-credit-usd", type=float, required=True)
    parser.add_argument("--hard-budget-usd", type=float, default=.5)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    tasks = build_tasks(); OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "tasks.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in tasks))
    budget = Budget(args.hard_budget_usd, 10, args.available_credit_usd, {KIMI: (.95, 4), MINIMAX: (.3, 1.2)})
    projected = sum(budget.cost(row["model"], math.ceil(len(row["prompt"]) / 3), cap(row)) for row in tasks)
    if projected > args.hard_budget_usd or args.available_credit_usd - args.hard_budget_usd < 10:
        raise SystemExit("cap-only budget preflight failed")
    _load_env_files((ROOT / ".env.fireworks", ROOT / ".env.fireworks.local"))
    key = os.getenv("FIREWORKS_API_KEY"); base = os.getenv("FIREWORKS_BASE_URL") or "https://api.fireworks.ai/inference/v1"
    if not key:
        raise SystemExit("FIREWORKS_API_KEY is required")
    ledger = AtomicLedger(OUT / "challenger-responses.jsonl")
    completed = {row["task_id"] for row in rows(OUT / "challenger-responses.jsonl") if row.get("ok")}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(call, row, key, base): row for row in tasks if row["task_id"] not in completed}
        for future in as_completed(futures):
            ledger.append(future.result())
    print(json.dumps({"tasks": len(tasks), "projected_usd": round(projected, 6)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
