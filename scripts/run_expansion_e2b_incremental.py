#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_e2b_regression_v2_inference import _request_e2b


def main() -> int:
    parser = argparse.ArgumentParser(description="Run E2B incrementally over generated Sprint 70 prompts.")
    parser.add_argument("--base-url", default="http://127.0.0.1:9379/v1")
    parser.add_argument("--model", default="gemma4-e2b")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout-s", type=float, default=120)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    args = parser.parse_args()
    plan = {row["target_id"]: row for row in _rows(ROOT / "evals/e2b-expansion-v1/plan.jsonl")}
    generated_by_target = {row["target_id"]: row for row in _rows(ROOT / "evals/e2b-expansion-v1/raw/generated-candidates.jsonl")}
    generated = list(generated_by_target.values())
    output = ROOT / "reports/generated/e2b-expansion-v1/e2b.jsonl"
    failures = ROOT / "reports/generated/e2b-expansion-v1/e2b-failures.jsonl"
    done = {row["task_id"]: row["prompt_sha256"] for row in _rows(output)}
    pending = [
        row for row in generated
        if done.get(plan[row["target_id"]]["task_id"]) != hashlib.sha256(row["prompt"].encode()).hexdigest()
    ]
    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        raise ValueError("Invalid E2B shard configuration.")
    pending = [
        row for row in pending
        if int.from_bytes(hashlib.sha256(plan[row["target_id"]]["task_id"].encode()).digest()[:4], "big") % args.shard_count
        == args.shard_index
    ]
    if args.limit is not None:
        pending = pending[:args.limit]
    completed = failed = 0
    def infer(candidate: dict) -> tuple[Path, dict]:
        target = plan[candidate["target_id"]]
        task_id, prompt = target["task_id"], candidate["prompt"]
        started = time.monotonic()
        try:
            answer = _request_e2b(args.base_url, args.model, prompt, args.timeout_s)
            path = output
            row = {
                "task_id": task_id, "answer": answer, "error": None,
                "latency_ms": (time.monotonic() - started) * 1000, "model": args.model,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "protocol": "raw-prompt-v1", "max_completion_tokens": 96,
            }
        except Exception as exc:
            path = failures
            row = {
                "task_id": task_id, "answer": None, "error": f"{type(exc).__name__}:{exc}",
                "latency_ms": (time.monotonic() - started) * 1000, "model": args.model,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "protocol": "raw-prompt-v1", "max_completion_tokens": 96,
            }
        return path, row
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for index, (path, row) in enumerate(pool.map(infer, pending), start=1):
            _append(path, row)
            if path == output:
                completed += 1
            else:
                failed += 1
            if index % 20 == 0:
                print(json.dumps({"processed": index, "completed": completed, "failed": failed}), flush=True)
    print(json.dumps({"available": len(generated), "attempted": len(pending), "completed": completed, "failed": failed}, sort_keys=True))
    return 0


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode()
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
