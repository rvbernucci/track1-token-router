#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
SYSTEM = (
    "Answer the user's task directly and correctly. Follow every explicit output-format "
    "constraint exactly. Return only the requested answer; do not add a preamble, explanation, "
    "or markdown unless the user explicitly requests it."
)
INTENT = {
    "factual_qa": "Give the shortest factually correct answer supported by stable knowledge.",
    "math_reasoning": "Solve the calculation carefully and return the requested final form.",
    "sentiment": "Classify only the requested text or aspect using exactly the allowed labels.",
    "summarization": "Preserve the essential facts while obeying the requested length and style.",
    "ner": "Extract only the requested named entities and preserve the required structure.",
    "code_debugging": "Return a corrected implementation that fixes the stated defect.",
    "logic_puzzle": "Solve the stated constraints and return only the requested conclusion.",
    "code_generation": "Return complete working code that satisfies the stated requirements.",
}


def messages(prompt: str, category: str, protocol: str) -> list[dict[str, str]]:
    if protocol == "raw":
        return [{"role": "user", "content": prompt}]
    instruction = SYSTEM
    if protocol == "intent_contract":
        instruction = f"{instruction} {INTENT[category]}"
    return [
        {"role": "system", "content": instruction},
        {"role": "user", "content": prompt},
    ]


def request(
    *, base_url: str, model: str, prompt: str, category: str, protocol: str,
    max_tokens: int, timeout: float,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages(prompt, category, protocol),
        "temperature": 0,
        "max_tokens": max_tokens,
        "max_completion_tokens": max_tokens,
    }
    started = perf_counter()
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        result = json.load(response)
    return {
        "answer": result["choices"][0]["message"]["content"].strip(),
        "latency_ms": round((perf_counter() - started) * 1000, 2),
    }


def load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def balanced_sample(tasks: list[dict[str, Any]], metadata: Mapping[str, Mapping[str, Any]], per_category: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for task in tasks:
        category = str(metadata[task["task_id"]]["category"])
        if counts.get(category, 0) >= per_category:
            continue
        selected.append({**task, "category": category})
        counts[category] = counts.get(category, 0) + 1
    if set(counts) != set(INTENT) or any(value != per_category for value in counts.values()):
        raise ValueError(f"cannot build balanced sample: {counts}")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=Path, default=ROOT / "evals/e2b-expansion-v1/splits/calibration.jsonl")
    parser.add_argument("--metadata", type=Path, default=ROOT / "evals/e2b-expansion-v1/metadata.jsonl")
    parser.add_argument("--references", type=Path, default=ROOT / "evals/e2b-expansion-v1/references/calibration.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/generated/e2b-prompt-ablation/results.jsonl")
    parser.add_argument("--base-url", default="http://127.0.0.1:19379/v1")
    parser.add_argument("--model", default="gemma4-e2b")
    parser.add_argument("--per-category", type=int, default=20)
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    metadata = {row["task_id"]: row for row in load_rows(args.metadata)}
    references = {row["task_id"]: row for row in load_rows(args.references)}
    tasks = balanced_sample(load_rows(args.tasks), metadata, args.per_category)
    plan = [(task, protocol) for task in tasks for protocol in ("raw", "contract", "intent_contract")]

    def run(item: tuple[dict[str, Any], str]) -> dict[str, Any]:
        task, protocol = item
        result = request(
            base_url=args.base_url, model=args.model, prompt=task["prompt"],
            category=task["category"], protocol=protocol,
            max_tokens=args.max_tokens, timeout=args.timeout,
        )
        return {
            "task_id": task["task_id"], "category": task["category"],
            "prompt": task["prompt"], "protocol": protocol,
            "reference_answer": references[task["task_id"]]["reference_answer"],
            "reference_rubric": references[task["task_id"]]["reference_rubric"],
            **result,
        }

    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run, item) for item in plan]
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda row: (row["task_id"], row["protocol"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))
    print(json.dumps({"rows": len(rows), "tasks": len(tasks), "protocols": 3}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
