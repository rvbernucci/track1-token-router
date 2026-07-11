#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.core.fireworks import FireworksClient
from router.core.prompts import build_answer_messages
from router.orchestration.final_validator import validate_or_safely_repair_final_answer
from router.orchestration.fireworks_model_router import normalize_fireworks_model_id


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the sealed Sprint 59 Fireworks baseline.")
    parser.add_argument("--candidates", type=Path, default=Path("evals/e2b-regression-v2-adjudication/sealed/final-holdout-candidates.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("evals/e2b-regression-v2-championship/sealed/fireworks-baseline.jsonl"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-tokens", type=int, default=192)
    parser.add_argument("--model", help="Optional exact allowed model ID for retry cohorts.")
    args = parser.parse_args(argv)
    api_key = os.getenv("FIREWORKS_API_KEY", "")
    base_url = os.getenv("FIREWORKS_BASE_URL", "")
    allowed = _allowed(os.getenv("ALLOWED_MODELS", ""))
    if not api_key or not base_url or not allowed:
        raise SystemExit("FIREWORKS_API_KEY, FIREWORKS_BASE_URL and ALLOWED_MODELS are required.")
    requested = normalize_fireworks_model_id(args.model) if args.model else ""
    if requested and requested not in allowed:
        raise SystemExit("--model must be present in ALLOWED_MODELS.")
    model = requested or _preferred(allowed)
    candidates = _jsonl(_absolute(args.candidates))
    output = _absolute(args.output)
    existing = {
        str(row["task_id"]): row
        for row in _jsonl(output)
        if output.exists() and not row.get("error") and str(row.get("answer") or "").strip()
    }
    pending = [row for row in candidates if str(row["task_id"]) not in existing]
    results = dict(existing)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(_run_one, row, api_key, base_url, model, args.max_tokens): str(row["task_id"])
            for row in pending
        }
        for future in as_completed(futures):
            row = future.result()
            results[str(row["task_id"])] = row
    ordered = [results[str(row["task_id"])] for row in candidates]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in ordered), encoding="utf-8")
    summary = {
        "rows": len(ordered),
        "errors": sum(bool(row.get("error")) for row in ordered),
        "prompt_tokens": sum(int(row["usage"]["prompt"]) for row in ordered),
        "completion_tokens": sum(int(row["usage"]["completion"]) for row in ordered),
        "total_tokens": sum(int(row["usage"]["total"]) for row in ordered),
        "models": dict(sorted(Counter(str(row["model"]) for row in ordered).items())),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["errors"] == 0 and summary["rows"] == 400 else 3


def _run_one(row: Mapping[str, Any], api_key: str, base_url: str, model: str, max_tokens: int) -> dict[str, Any]:
    task_id = str(row["task_id"])
    prompt = str(row["task_text"])
    task = TaskEnvelope(id=task_id, input_text=prompt)
    client = FireworksClient(base_url=base_url, model=model, api_key=api_key, timeout_s=45, max_retries=2, retry_sleep_s=0.5)
    started = perf_counter()
    try:
        response = client.complete(build_answer_messages(task, mode="concise"), temperature=0.0, max_tokens=max_tokens)
        contract = validate_or_safely_repair_final_answer(task, response.text)
        answer = contract.repaired_answer or response.text.strip()
        return {
            "schema_version": "e2b-v2-fireworks-baseline-v1",
            "task_id": task_id,
            "answer": answer,
            "raw_answer": response.text,
            "contract": contract.to_dict(),
            "model": model,
            "usage": response.usage.to_dict(),
            "latency_ms": (perf_counter() - started) * 1000,
            "error": None,
        }
    except Exception as exc:
        return {
            "schema_version": "e2b-v2-fireworks-baseline-v1",
            "task_id": task_id,
            "answer": "",
            "raw_answer": "",
            "contract": None,
            "model": model,
            "usage": {"prompt": 0, "completion": 0, "total": 0},
            "latency_ms": (perf_counter() - started) * 1000,
            "error": f"{type(exc).__name__}:{str(exc)[:160]}",
        }


def _preferred(allowed: Sequence[str]) -> str:
    for suffix in ("minimax-m3", "kimi-k2p7-code"):
        for model in allowed:
            if model.endswith(suffix):
                return model
    return allowed[0]


def _allowed(raw: str) -> list[str]:
    values = [item.strip() for item in raw.replace("\n", ",").split(",") if item.strip()]
    return [normalize_fireworks_model_id(item) for item in values]


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
