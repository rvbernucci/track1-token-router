#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
from queue import Queue
import sys
from threading import Lock
from time import perf_counter
from typing import Any
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.core.e2b_runner import E2B_PROMPT_VERSION, build_e2b_messages
from router.orchestration.final_validator import apply_answer_contract


SCHEMA_VERSION = "e2b-contract-population-v1"


def rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def population(root: Path, *, include_protected: bool = True) -> list[dict[str, Any]]:
    ledger = {row["task_id"]: row for row in rows(root / "evals/router-ml-v3/ledger.jsonl")}
    tasks: dict[str, dict[str, Any]] = {}
    refs: dict[str, dict[str, Any]] = {}
    task_paths = [
        *sorted((root / "evals/e2b-expansion-v1/splits").glob("*.jsonl")),
        root / "evals/e2b-regression-v2/inputs/train.jsonl",
        root / "evals/e2b-regression-v2/inputs/validation.jsonl",
    ]
    ref_paths = [
        *sorted((root / "evals/e2b-expansion-v1/references").glob("*.jsonl")),
        *sorted((root / "evals/e2b-regression-v2/references").glob("*.jsonl")),
    ]
    if include_protected:
        task_paths.extend(
            (
                root / "evals/e2b-expansion-v1/sealed/tasks/final_holdout.jsonl",
                root / "evals/e2b-regression-v2/inputs/final_holdout.jsonl",
            )
        )
        ref_paths.extend(
            (
                root / "evals/e2b-expansion-v1/sealed/references/final_holdout.jsonl",
                root / "evals/e2b-regression-v2/sealed/final_holdout.jsonl",
            )
        )
    for path in task_paths:
        for row in rows(path):
            tasks[str(row["task_id"])] = row
    for path in ref_paths:
        for row in rows(path):
            refs[str(row["task_id"])] = row
    expected = {
        task_id
        for task_id, row in ledger.items()
        if include_protected or row.get("role") != "protected_holdout"
    }
    if set(tasks) != expected or set(refs) != expected:
        raise ValueError(
            f"Population join mismatch: ledger={len(ledger)} tasks={len(tasks)} refs={len(refs)}"
        )
    result = []
    for task_id in sorted(expected):
        task, reference, evidence = tasks[task_id], refs[task_id], ledger[task_id]
        result.append(
            {
                "task_id": task_id,
                "prompt": str(task["prompt"]),
                "reference_answer": str(reference["reference_answer"]),
                "reference_rubric": str(reference["reference_rubric"]),
                "output_shape": reference.get("output_shape"),
                "role": evidence["role"],
                "category": evidence["category"],
                "intent": evidence["intent"],
                "lineage": evidence["lineage"],
                "features": evidence["features"],
            }
        )
    return result


def request(endpoint: str, model: str, prompt: str, timeout: float) -> tuple[str, float]:
    payload = {
        "model": model,
        "messages": build_e2b_messages(prompt),
        "temperature": 0,
        "max_tokens": 96,
        "max_completion_tokens": 96,
    }
    started = perf_counter()
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = json.load(response)
    answer = body["choices"][0]["message"]["content"]
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("E2B returned an empty answer")
    return answer.strip(), (perf_counter() - started) * 1000


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoints", required=True)
    parser.add_argument("--model", default="gemma4-e2b")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-indices", default="0")
    args = parser.parse_args()
    endpoints = [item.strip() for item in args.endpoints.split(",") if item.strip()]
    if not endpoints or args.workers < 1:
        raise ValueError("At least one endpoint and worker are required")
    if args.shard_count < 1:
        raise ValueError("shard-count must be positive")
    shard_indices = {int(value) for value in args.shard_indices.split(",") if value.strip()}
    if not shard_indices or min(shard_indices) < 0 or max(shard_indices) >= args.shard_count:
        raise ValueError("shard-indices must fall inside shard-count")
    all_tasks = [
        task
        for task in population(ROOT)
        if int(hashlib.sha256(task["task_id"].encode()).hexdigest(), 16) % args.shard_count in shard_indices
    ]
    done = {row["task_id"] for row in rows(args.output)} if args.resume else set()
    if args.output.exists() and not args.resume:
        raise ValueError("Output exists; use --resume")
    queue: Queue[str] = Queue()
    for endpoint in endpoints:
        queue.put(endpoint)
    lock = Lock()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def run(task: dict[str, Any]) -> dict[str, Any]:
        endpoint = queue.get()
        try:
            try:
                answer, latency = request(endpoint, args.model, task["prompt"], args.timeout)
                envelope = TaskEnvelope(id=task["task_id"], input_text=task["prompt"])
                contract = apply_answer_contract(envelope, answer)
                return {
                    **task,
                    "schema_version": SCHEMA_VERSION,
                    "prompt_sha256": hashlib.sha256(task["prompt"].encode()).hexdigest(),
                    "prompt_version": E2B_PROMPT_VERSION,
                    "raw_answer": answer,
                    "post_contract_answer": contract.answer if contract.valid else answer,
                    "answer_contract": contract.to_dict(),
                    "latency_ms": latency,
                    "endpoint": endpoint,
                    "error": None,
                }
            except Exception as exc:
                return {
                    **task,
                    "schema_version": SCHEMA_VERSION,
                    "prompt_sha256": hashlib.sha256(task["prompt"].encode()).hexdigest(),
                    "prompt_version": E2B_PROMPT_VERSION,
                    "raw_answer": None,
                    "post_contract_answer": None,
                    "answer_contract": None,
                    "latency_ms": None,
                    "endpoint": endpoint,
                    "error": f"{type(exc).__name__}:{exc}",
                }
        finally:
            queue.put(endpoint)

    pending = [task for task in all_tasks if task["task_id"] not in done]
    written = 0
    with ThreadPoolExecutor(max_workers=min(args.workers, len(endpoints))) as pool:
        futures = [pool.submit(run, task) for task in pending]
        for future in as_completed(futures):
            record = future.result()
            with lock, args.output.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            written += 1
            if written % 100 == 0:
                print(json.dumps({"written": written, "remaining": len(pending) - written}), flush=True)
    print(
        json.dumps(
            {
                "population": len(all_tasks),
                "written": written,
                "resumed": len(done),
                "shard_count": args.shard_count,
                "shard_indices": sorted(shard_indices),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
