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

from scripts.functiongemma_openai_evaluate import assessment_from_openai_response, request_assessment
from router.orchestration.assessment import approximate_token_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Run FunctionGemma incrementally over generated Sprint 70 prompts.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8091/v1")
    parser.add_argument("--model", default="functiongemma-q8")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout-s", type=float, default=30)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--force-min-prompt-tokens", type=int)
    parser.add_argument("--runtime-id", default="functiongemma-unspecified-runtime")
    args = parser.parse_args()
    plan = {row["target_id"]: row for row in _rows(ROOT / "evals/e2b-expansion-v1/plan.jsonl")}
    generated_by_target = {row["target_id"]: row for row in _rows(ROOT / "evals/e2b-expansion-v1/raw/generated-candidates.jsonl")}
    generated = list(generated_by_target.values())
    output = ROOT / "reports/generated/e2b-expansion-v1/functiongemma.jsonl"
    failures = ROOT / "reports/generated/e2b-expansion-v1/functiongemma-failures.jsonl"
    # Successful rows are immutable. Failed parses remain retryable because
    # FunctionGemma decoding can recover on a later deterministic invocation.
    done = {row["task_id"]: row["prompt_sha256"] for row in _rows(output)}
    failure_attempts: dict[tuple[str, str], int] = {}
    for row in _rows(failures):
        key = (str(row["task_id"]), str(row["prompt_sha256"]))
        failure_attempts[key] = failure_attempts.get(key, 0) + 1
    pending = []
    for row in generated:
        task_id = plan[row["target_id"]]["task_id"]
        prompt_hash = hashlib.sha256(row["prompt"].encode()).hexdigest()
        forced = args.force_min_prompt_tokens is not None and approximate_token_count(row["prompt"]) > args.force_min_prompt_tokens
        if forced or (
            done.get(task_id) != prompt_hash and failure_attempts.get((task_id, prompt_hash), 0) < 3
        ):
            pending.append(row)
    if args.limit is not None:
        pending = pending[:args.limit]
    completed = failed = 0
    def infer(candidate: dict) -> tuple[Path, dict]:
        target = plan[candidate["target_id"]]
        task_id, prompt = target["task_id"], candidate["prompt"]
        started = time.monotonic()
        try:
            response = request_assessment(
                base_url=args.base_url, model=args.model, task_text=prompt, max_tokens=64, timeout_s=args.timeout_s,
            )
            assessment = assessment_from_openai_response(response).to_dict()
            row = {
                "task_id": task_id, "assessment": assessment, "error": None,
                "latency_ms": (time.monotonic() - started) * 1000, "model": args.model,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "protocol": "raw-prompt-v1",
                "runtime_id": args.runtime_id,
            }
            return output, row
        except Exception as exc:
            return failures, {
                "task_id": task_id, "assessment": None, "error": f"{type(exc).__name__}:{exc}",
                "latency_ms": (time.monotonic() - started) * 1000, "model": args.model,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "protocol": "raw-prompt-v1",
                "runtime_id": args.runtime_id,
            }
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = pool.map(infer, pending)
        for index, (path, row) in enumerate(results, start=1):
            _append(path, row)
            if path == output:
                completed += 1
            else:
                failed += 1
            if index % 100 == 0:
                print(json.dumps({"processed": index, "completed": completed, "failed": failed}), flush=True)
    print(json.dumps({"available": len(generated), "attempted": len(pending), "completed": completed, "failed": failed}, sort_keys=True))
    return 0


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


if __name__ == "__main__":
    raise SystemExit(main())
