#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.dataset_forge.e2b_expansion import (
    ExpansionPaths, build_targets, generate, materialize, summary, verify_manifest, write_plan,
)
from router.dataset_forge.providers import ProviderError, provider_from_env


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Sprint 70 E2B expansion corpus.")
    parser.add_argument("--root", type=Path, default=Path("evals/e2b-expansion-v1"))
    parser.add_argument("--env-file", action="append", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--materialize", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--agy-batch-size", type=int)
    parser.add_argument("--fireworks-batch-size", type=int)
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--max-batches", type=int)
    parser.add_argument("--fireworks-budget-usd", type=float, default=8.0)
    parser.add_argument("--retry-target-ids-file", type=Path)
    args = parser.parse_args()
    _load_env(args.env_file or [Path(".env.dataset-forge.local"), Path(".env.fireworks.local")])
    paths = ExpansionPaths(_absolute(args.root))
    targets = build_targets()
    write_plan(paths, targets)
    result: dict[str, object] = {"plan": summary(targets), "executed": False}
    try:
        if args.execute:
            providers = {
                name: provider_from_env(name, role="e2b_expansion_generator", max_tokens=8192)
                for name in ("agy", "fireworks")
            }
            result["generation"] = generate(
                targets=targets, providers=providers, paths=paths, batch_size=args.batch_size,
                max_workers=args.max_workers, fireworks_budget_usd=args.fireworks_budget_usd,
                max_batches=args.max_batches,
                provider_batch_sizes={
                    "agy": args.agy_batch_size or args.batch_size,
                    "fireworks": args.fireworks_batch_size or args.batch_size,
                },
                force_target_ids=_read_ids(args.retry_target_ids_file),
            )
            result["executed"] = True
        if args.materialize:
            result["manifest"] = materialize(targets=targets, paths=paths)
        if args.check:
            result["verification"] = verify_manifest(paths)
    except (OSError, ProviderError, ValueError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _load_env(paths: list[Path]) -> None:
    for path in paths:
        resolved = _absolute(path)
        if not resolved.is_file():
            continue
        for line in resolved.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _read_ids(path: Path | None) -> set[str]:
    if path is None:
        return set()
    resolved = _absolute(path)
    return {line.strip() for line in resolved.read_text(encoding="utf-8").splitlines() if line.strip()}


if __name__ == "__main__":
    raise SystemExit(main())
