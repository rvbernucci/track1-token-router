#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import threading
import time
import math
from collections import Counter, deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.core.fireworks import FireworksClient
from router.core.fireworks_runner import _completion_token_policy
from router.core.model_client import ModelClientError
from router.orchestration.fireworks_model_router import normalize_fireworks_model_id
from scripts.fireworks_microbench import _load_env_files

MODELS = (
    "accounts/fireworks/models/kimi-k2p7-code",
    "accounts/fireworks/models/minimax-m3",
)
DOMAIN = {
    "factual_qa": "current_factual", "math_reasoning": "math_reasoning",
    "sentiment": "classification", "summarization": "summarization",
    "ner": "extraction", "code_debugging": "coding", "logic_puzzle": "logic",
    "code_generation": "coding",
}


@dataclass(frozen=True)
class Budget:
    hard_usd: float
    reserve_usd: float
    available_usd: float
    rates: dict[str, tuple[float, float]]

    def cost(self, model: str, prompt: int, completion: int) -> float:
        input_rate, output_rate = self.rates[model]
        return (prompt * input_rate + completion * output_rate) / 1_000_000


class AtomicLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._thread_lock = threading.Lock()

    def append(self, row: dict[str, Any]) -> None:
        encoded = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        with self._thread_lock, self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _usage(row: dict[str, Any]) -> tuple[int, int]:
    usage = row.get("usage") or {}
    return int(usage.get("prompt", 0)), int(usage.get("completion", 0))


def _call(task: dict[str, Any], model: str, *, api_key: str, base_url: str, timeout: float, retries: int) -> dict[str, Any]:
    envelope = TaskEnvelope(id=task["task_id"], input_text=task["prompt"])
    policy = _completion_token_policy(envelope, tier="balanced", domain=DOMAIN[task["category"]], configured_max_tokens=512)
    client = FireworksClient(base_url=base_url, model=model, api_key=api_key, timeout_s=timeout, max_retries=retries)
    started = perf_counter()
    try:
        response = client.complete(
            [{"role": "user", "content": task["prompt"]}],
            temperature=0.0,
            max_tokens=int(policy["max_tokens"]),
            extra_body={"reasoning_effort": "none", "user": "proofroute-fireworks-champion-v3"},
        )
        return {
            "schema_version": "fireworks-champion-v3-response-v1", "task_id": task["task_id"],
            "model": model, "answer": response.text, "ok": bool(response.text.strip()),
            "finish_reason": response.raw.get("choices", [{}])[0].get("finish_reason") if isinstance(response.raw, dict) else None,
            "usage": response.usage.to_dict(), "latency_ms": round((perf_counter() - started) * 1000, 2),
            "request": {"temperature": 0.0, "reasoning_effort": "none", "max_tokens": policy["max_tokens"], "raw_prompt_sha256": task["prompt_sha256"]},
            "error": None,
        }
    except ModelClientError as exc:
        return {
            "schema_version": "fireworks-champion-v3-response-v1", "task_id": task["task_id"],
            "model": model, "answer": "", "ok": False, "finish_reason": None,
            "usage": {"prompt": 0, "completion": 0, "total": 0},
            "latency_ms": round((perf_counter() - started) * 1000, 2),
            "request": {"temperature": 0.0, "reasoning_effort": "none", "max_tokens": policy["max_tokens"], "raw_prompt_sha256": task["prompt_sha256"]},
            "error": str(exc)[:500],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resumable paired Fireworks champion arena")
    parser.add_argument("--tasks", type=Path, default=Path("evals/fireworks-champion-v3/tasks.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("reports/generated/fireworks-champion-v3/responses.jsonl"))
    parser.add_argument("--kimi-concurrency", type=int, default=3)
    parser.add_argument("--minimax-concurrency", type=int, default=3)
    parser.add_argument("--timeout-s", type=float, default=120)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--max-failure-rate", type=float, default=0.08)
    parser.add_argument("--max-runtime-s", type=float, default=18000)
    parser.add_argument("--target-budget-usd", type=float, default=5.0)
    parser.add_argument("--hard-budget-usd", type=float, default=7.0)
    parser.add_argument("--reserve-usd", type=float, default=10.0)
    parser.add_argument("--available-credit-usd", type=float, required=True)
    parser.add_argument("--kimi-input-usd-per-million", type=float, default=0.95)
    parser.add_argument("--kimi-output-usd-per-million", type=float, default=4.0)
    parser.add_argument("--minimax-input-usd-per-million", type=float, default=0.3)
    parser.add_argument("--minimax-output-usd-per-million", type=float, default=1.2)
    parser.add_argument("--max-pairs", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    concurrency = {MODELS[0]: args.kimi_concurrency, MODELS[1]: args.minimax_concurrency}
    if any(not 1 <= value <= 8 for value in concurrency.values()):
        raise SystemExit("per-model concurrency must be 1..8")
    budget = Budget(args.hard_budget_usd, args.reserve_usd, args.available_credit_usd, {
        MODELS[0]: (args.kimi_input_usd_per_million, args.kimi_output_usd_per_million),
        MODELS[1]: (args.minimax_input_usd_per_million, args.minimax_output_usd_per_million),
    })
    if args.target_budget_usd > budget.hard_usd:
        raise SystemExit("target budget exceeds hard budget")
    if budget.available_usd - budget.reserve_usd <= 0 or budget.hard_usd > budget.available_usd - budget.reserve_usd:
        raise SystemExit("budget violates the required credit reserve")

    tasks_path = args.tasks if args.tasks.is_absolute() else ROOT / args.tasks
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    tasks = _rows(tasks_path)
    if len(tasks) != 800:
        raise SystemExit(f"expected 800 frozen tasks, got {len(tasks)}")
    prior = _rows(output_path)
    completed = {(row["task_id"], row["model"]) for row in prior if row.get("ok")}
    spent = sum(budget.cost(row["model"], *_usage(row)) for row in prior)
    pending = [(task, model) for task in tasks for model in MODELS if (task["task_id"], model) not in completed]
    if args.max_pairs is not None:
        pending = pending[: max(0, args.max_pairs)]
    projected = spent
    for task, model in pending:
        envelope = TaskEnvelope(id=task["task_id"], input_text=task["prompt"])
        policy = _completion_token_policy(envelope, tier="balanced", domain=DOMAIN[task["category"]], configured_max_tokens=512)
        conservative_input = math.ceil(len(task["prompt"]) / 3)
        projected += budget.cost(model, conservative_input, int(policy["max_tokens"]))
    summary = {"tasks": len(tasks), "completed": len(completed), "pending": len(pending), "spent_usd": round(spent, 6), "conservative_projected_usd": round(projected, 6), "target_budget_usd": args.target_budget_usd, "hard_budget_usd": budget.hard_usd, "dry_run": args.dry_run}
    print(json.dumps(summary, sort_keys=True), flush=True)
    if projected > args.target_budget_usd:
        raise SystemExit("conservative preflight exceeds target experiment budget; no live calls made")
    if args.dry_run or not pending:
        return 0

    _load_env_files((ROOT / ".env.fireworks", ROOT / ".env.fireworks.local"))
    api_key = os.getenv("FIREWORKS_API_KEY")
    base_url = os.getenv("FIREWORKS_BASE_URL") or "https://api.fireworks.ai/inference/v1"
    allowed = {normalize_fireworks_model_id(value.strip()) for value in os.getenv("ALLOWED_MODELS", "").split(",") if value.strip()}
    if not api_key:
        raise SystemExit("FIREWORKS_API_KEY is not set")
    if allowed and not set(MODELS).issubset(allowed):
        raise SystemExit("ALLOWED_MODELS does not authorize both arena models")

    ledger = AtomicLedger(output_path)
    started = time.monotonic()
    attempted = failures = 0
    projected_average = max(spent / max(1, len(prior)), 0.0005)
    executors = {model: ThreadPoolExecutor(max_workers=concurrency[model]) for model in MODELS}
    active_by_model = Counter()
    futures: dict[Any, tuple[dict[str, Any], str]] = {}
    queues = {model: deque((task, candidate) for task, candidate in pending if candidate == model) for model in MODELS}
    stop_reason: str | None = None
    try:
        while True:
            while len(futures) < sum(concurrency.values()):
                available_model = next((model for model in MODELS if queues[model] and active_by_model[model] < concurrency[model]), None)
                if available_model is None:
                    break
                task, model = queues[available_model].popleft()
                task_policy = _completion_token_policy(TaskEnvelope(id=task["task_id"], input_text=task["prompt"]), tier="balanced", domain=DOMAIN[task["category"]], configured_max_tokens=512)
                next_call_ceiling = budget.cost(model, math.ceil(len(task["prompt"]) / 3), int(task_policy["max_tokens"]))
                if spent + next_call_ceiling > budget.hard_usd:
                    stop_reason = "projected_budget_limit"
                    break
                futures[executors[model].submit(_call, task, model, api_key=api_key, base_url=base_url, timeout=args.timeout_s, retries=args.max_retries)] = (task, model)
                active_by_model[model] += 1
            if not futures or stop_reason:
                break
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                _, finished_model = futures.pop(future)
                active_by_model[finished_model] -= 1
                row = future.result()
                ledger.append(row)
                attempted += 1
                failures += int(not row["ok"])
                spent += budget.cost(row["model"], *_usage(row))
                projected_average = spent / max(1, len(prior) + attempted)
                print(json.dumps({"task_id": row["task_id"], "model": row["model"], "ok": row["ok"], "spent_usd": round(spent, 6)}), flush=True)
            if attempted >= 20 and failures / attempted > args.max_failure_rate:
                stop_reason = "failure_rate_limit"
            if time.monotonic() - started > args.max_runtime_s:
                stop_reason = "runtime_limit"
    finally:
        for executor in executors.values():
            executor.shutdown(wait=True, cancel_futures=True)
    print(json.dumps({"attempted": attempted, "failures": failures, "spent_usd": round(spent, 6), "stop_reason": stop_reason}, sort_keys=True))
    return 2 if stop_reason else 0


if __name__ == "__main__":
    raise SystemExit(main())
