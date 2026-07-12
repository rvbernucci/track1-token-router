#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.dataset_forge.providers import FireworksDatasetProvider
from scripts.judge_engine_outcomes import (
    _cumulative_model_cost,
    _exclusive_output_lock,
    _jsonl,
    run_judging,
)

MODEL = "accounts/fireworks/models/glm-5p2"
DEFAULT_WORKERS = 16


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Resume-safe parallel GLM-5.2 candidate adjudication.")
    value.add_argument("--candidates", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    value.add_argument("--max-concurrency", type=int)
    value.add_argument("--batch-size", type=int, default=20)
    value.add_argument("--max-tokens", type=int, default=1536)
    value.add_argument("--budget-usd", type=float, default=20.0)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    _load_env(ROOT / ".env.fireworks.local")
    _load_env(ROOT / ".env.fireworks")
    api_key = os.getenv("FIREWORKS_API_KEY", "")
    if not api_key:
        raise SystemExit("FIREWORKS_API_KEY is not set.")
    base_url = os.getenv("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")

    def factory(_: int) -> FireworksDatasetProvider:
        return FireworksDatasetProvider(
            api_key=api_key,
            base_url=base_url,
            model=MODEL,
            max_tokens=args.max_tokens,
        )

    result = run_parallel(
        candidates_path=args.candidates,
        output=args.output,
        provider_factory=factory,
        workers=args.workers,
        max_concurrency=args.max_concurrency,
        batch_size=args.batch_size,
        budget_usd=args.budget_usd,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["remaining"] == 0 else 3


def run_parallel(
    *,
    candidates_path: Path,
    output: Path,
    provider_factory: Callable[[int], Any],
    workers: int = DEFAULT_WORKERS,
    max_concurrency: int | None = None,
    batch_size: int = 20,
    budget_usd: float = 20.0,
) -> dict[str, Any]:
    if workers < 1:
        raise ValueError("workers must be positive")
    concurrency = workers if max_concurrency is None else max_concurrency
    if not 1 <= concurrency <= workers:
        raise ValueError("max_concurrency must be between 1 and workers")
    if not 20 <= batch_size <= 25:
        raise ValueError("batch_size must be between 20 and 25")
    if budget_usd < 0:
        raise ValueError("budget_usd must be non-negative")

    candidates = [row for row in _jsonl(candidates_path) if not row.get("failure") and not row.get("refusal")]
    ids = [str(row["id"]) for row in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate ids must be unique")
    parts_dir = Path(str(output) + ".parts")
    parts_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    with _exclusive_output_lock(output):
        canonical = _jsonl(output)
        part_paths = [parts_dir / f"worker-{index:02d}.jsonl" for index in range(workers)]
        all_existing = _deduplicate([*canonical, *(row for path in part_paths for row in _jsonl(path))])
        spent_before = _unique_model_cost(all_existing, MODEL)
        if spent_before > budget_usd + 1e-12:
            raise ValueError("existing cumulative spend exceeds --budget-usd")
        remaining_budget = max(0.0, budget_usd - spent_before)
        per_worker_new_budget = remaining_budget / workers
        completed = {
            str(row["candidate_id"])
            for row in all_existing
            if row.get("judge_model") == MODEL and row.get("candidate_id")
        }

        shards: list[list[Mapping[str, Any]]] = [[] for _ in range(workers)]
        for row in candidates:
            if str(row["id"]) not in completed:
                shards[_shard(str(row["id"]), workers)].append(row)
        for shard in shards:
            shard.sort(key=lambda row: str(row["id"]))

        def worker(index: int) -> dict[str, Any]:
            candidate_path = parts_dir / f"worker-{index:02d}-candidates.jsonl"
            _write_jsonl(candidate_path, shards[index])
            part_path = part_paths[index]
            part_spent = _cumulative_model_cost(_jsonl(part_path), MODEL)
            provider = provider_factory(index)
            if str(provider.model) != MODEL:
                raise ValueError(f"worker {index} provider is not pinned to {MODEL}")
            if not callable(getattr(provider, "estimate_upper_bound_usd", None)):
                raise ValueError(f"worker {index} provider cannot enforce a hard pre-call budget")
            if not shards[index]:
                return {"worker": index, "written": 0, "remaining": 0, "billable_cost_usd": 0.0}
            result = run_judging(
                candidates_path=candidate_path,
                output=part_path,
                provider=provider,
                batch_size=batch_size,
                budget_usd=part_spent + per_worker_new_budget,
            )
            return {"worker": index, **result}

        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="glm-judge") as executor:
            futures = [executor.submit(worker, index) for index in range(workers)]
            for future in as_completed(futures):
                results.append(future.result())

        merged = _deduplicate([*canonical, *(row for path in part_paths for row in _jsonl(path))])
        merged.sort(key=lambda row: (str(row.get("candidate_id", "")), str(row.get("judge_model", ""))))
        _write_jsonl(output, merged)
        cumulative = _unique_model_cost(merged, MODEL)
        if cumulative > budget_usd + 1e-9:
            raise RuntimeError("aggregate Fireworks spend exceeded the hard budget")
        completed_after = {
            str(row["candidate_id"])
            for row in merged
            if row.get("judge_model") == MODEL and row.get("candidate_id")
        }
        return {
            "schema_version": "parallel-fireworks-judges-v1",
            "model": MODEL,
            "workers": workers,
            "batch_size": batch_size,
            "candidates": len(candidates),
            "already_complete": len(set(ids) & completed),
            "written": len((set(ids) & completed_after) - completed),
            "remaining": len(set(ids) - completed_after),
            "billable_cost_usd": max(0.0, cumulative - spent_before),
            "cumulative_billable_cost_usd": cumulative,
            "budget_usd": budget_usd,
            "per_worker_new_budget_usd": per_worker_new_budget,
            "worker_results": sorted(results, key=lambda row: int(row["worker"])),
        }


def _shard(candidate_id: str, workers: int) -> int:
    return int(hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:16], 16) % workers


def _deduplicate(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("candidate_id", "")), str(row.get("judge_model", "")))
        if all(key):
            result.setdefault(key, dict(row))
    return list(result.values())


def _unique_model_cost(rows: Sequence[Mapping[str, Any]], model: str) -> float:
    unique_requests: dict[str, Mapping[str, Any]] = {}
    anonymous: list[Mapping[str, Any]] = []
    for row in rows:
        if row.get("judge_model") != model:
            continue
        provenance = row.get("provenance")
        request_id = provenance.get("request_id") if isinstance(provenance, Mapping) else None
        if isinstance(request_id, str) and request_id:
            unique_requests.setdefault(request_id, row)
        else:
            anonymous.append(row)
    return _cumulative_model_cost([*unique_requests.values(), *anonymous], model)


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(str(path) + ".tmp")
    temporary.write_text(
        "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


if __name__ == "__main__":
    raise SystemExit(main())
