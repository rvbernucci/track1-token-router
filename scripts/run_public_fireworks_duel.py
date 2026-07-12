#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.fireworks import FireworksClient
from router.core.fireworks_runner import _completion_token_policy
from router.core.contracts import TaskEnvelope
from router.core.model_client import ModelClientError
from router.orchestration.fireworks_model_router import normalize_fireworks_model_id
from scripts.fireworks_microbench import _load_env_files

MODELS = (
    "accounts/fireworks/models/minimax-m3",
    "accounts/fireworks/models/kimi-k2p7-code",
)
DOMAINS = {
    "T01": "factual_qa", "T01b": "factual_qa", "T01c": "factual_qa",
    "T02": "math_reasoning", "T02b": "math_reasoning",
    "T03": "sentiment", "T03b": "sentiment",
    "T04": "summarization", "T04b": "summarization", "T05": "ner",
}
def main() -> int:
    parser = argparse.ArgumentParser(description="Run a blind paired duel on the retired Track 1 sample.")
    parser.add_argument("--tasks", type=Path, default=Path("evals/public-retired-track1/tasks.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/generated/public-fireworks-duel-v2"))
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument("--seed", type=int, default=66066)
    args = parser.parse_args()

    _load_env_files((ROOT / ".env.fireworks", ROOT / ".env.fireworks.local"))
    api_key = os.getenv("FIREWORKS_API_KEY")
    if not api_key:
        raise SystemExit("FIREWORKS_API_KEY is not set")
    base_url = os.getenv("FIREWORKS_BASE_URL") or "https://api.fireworks.ai/inference/v1"

    tasks = json.loads((ROOT / args.tasks).read_text(encoding="utf-8"))
    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "results.json"
    results = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else []
    completed = {(row["task_id"], row["model"]) for row in results}
    for task in tasks:
        envelope = TaskEnvelope(id=task["task_id"], input_text=task["prompt"])
        policy = _completion_token_policy(
            envelope,
            tier="balanced",
            domain=DOMAINS[task["task_id"]],
            configured_max_tokens=512,
        )
        for model in MODELS:
            if (task["task_id"], model) in completed:
                continue
            client = FireworksClient(
                base_url=base_url,
                model=normalize_fireworks_model_id(model),
                api_key=api_key,
                timeout_s=args.timeout_s,
                max_retries=1,
            )
            started = perf_counter()
            try:
                response = client.complete(
                    [{"role": "user", "content": task["prompt"]}],
                    temperature=0.0,
                    max_tokens=int(policy["max_tokens"]),
                    extra_body={"reasoning_effort": "none", "user": "track1-token-router-v1"},
                )
                row = {
                    "task_id": task["task_id"],
                    "model": model,
                    "answer": response.text.strip(),
                    "usage": response.usage.to_dict(),
                    "latency_ms": round((perf_counter() - started) * 1000, 2),
                    "max_tokens": policy["max_tokens"],
                    "ok": True,
                }
            except ModelClientError as exc:
                row = {
                    "task_id": task["task_id"], "model": model, "answer": "",
                    "usage": {"prompt": 0, "completion": 0, "total": 0},
                    "latency_ms": round((perf_counter() - started) * 1000, 2),
                    "max_tokens": policy["max_tokens"], "ok": False, "error": str(exc),
                }
            results.append(row)
            completed.add((task["task_id"], model))
            results_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"task_id": task["task_id"], "model": model, "done": True}), flush=True)

    rng = random.Random(args.seed)
    by_task = {task["task_id"]: {"task_id": task["task_id"], "prompt": task["prompt"]} for task in tasks}
    answer_key = {}
    for task_id, row in by_task.items():
        candidates = [result for result in results if result["task_id"] == task_id]
        rng.shuffle(candidates)
        row["candidate_a"] = candidates[0]["answer"]
        row["candidate_b"] = candidates[1]["answer"]
        answer_key[task_id] = {"candidate_a": candidates[0]["model"], "candidate_b": candidates[1]["model"]}
    (output_dir / "blind-candidates.json").write_text(
        json.dumps(list(by_task.values()), indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "answer-key.json").write_text(json.dumps(answer_key, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
