#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_MEMORY_LIMIT_MB = 4096
DEFAULT_RUNTIME_OVERHEAD_MB = 512
DEFAULT_KV_CACHE_MB = 256
DEFAULT_SAFETY_MARGIN_MB = 384


@dataclass(frozen=True)
class EnvelopeEstimate:
    ok: bool
    model_size_mb: float
    runtime_overhead_mb: int
    kv_cache_mb: int
    safety_margin_mb: int
    memory_limit_mb: int
    estimated_total_mb: float
    headroom_mb: float


def estimate_envelope(
    *,
    model_size_mb: float,
    runtime_overhead_mb: int = DEFAULT_RUNTIME_OVERHEAD_MB,
    kv_cache_mb: int = DEFAULT_KV_CACHE_MB,
    safety_margin_mb: int = DEFAULT_SAFETY_MARGIN_MB,
    memory_limit_mb: int = DEFAULT_MEMORY_LIMIT_MB,
) -> EnvelopeEstimate:
    estimated_total_mb = model_size_mb + runtime_overhead_mb + kv_cache_mb + safety_margin_mb
    headroom_mb = memory_limit_mb - estimated_total_mb
    return EnvelopeEstimate(
        ok=headroom_mb >= 0,
        model_size_mb=round(model_size_mb, 2),
        runtime_overhead_mb=runtime_overhead_mb,
        kv_cache_mb=kv_cache_mb,
        safety_margin_mb=safety_margin_mb,
        memory_limit_mb=memory_limit_mb,
        estimated_total_mb=round(estimated_total_mb, 2),
        headroom_mb=round(headroom_mb, 2),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Estimate whether a local model fits the Track 1 memory envelope.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--model-file", type=Path, help="Path to a local model file to size.")
    source.add_argument("--model-size-mb", type=float, help="Model size estimate in MiB.")
    parser.add_argument("--memory-limit-mb", type=int, default=DEFAULT_MEMORY_LIMIT_MB)
    parser.add_argument("--runtime-overhead-mb", type=int, default=DEFAULT_RUNTIME_OVERHEAD_MB)
    parser.add_argument("--kv-cache-mb", type=int, default=DEFAULT_KV_CACHE_MB)
    parser.add_argument("--safety-margin-mb", type=int, default=DEFAULT_SAFETY_MARGIN_MB)
    parser.add_argument("--check", action="store_true", help="Exit non-zero when the estimate does not fit.")
    args = parser.parse_args()

    model_size_mb = args.model_size_mb
    if args.model_file is not None:
        model_size_mb = args.model_file.stat().st_size / (1024 * 1024)

    estimate = estimate_envelope(
        model_size_mb=float(model_size_mb),
        runtime_overhead_mb=args.runtime_overhead_mb,
        kv_cache_mb=args.kv_cache_mb,
        safety_margin_mb=args.safety_margin_mb,
        memory_limit_mb=args.memory_limit_mb,
    )
    print(json.dumps(asdict(estimate), sort_keys=True))
    return 0 if estimate.ok or not args.check else 1


if __name__ == "__main__":
    raise SystemExit(main())
