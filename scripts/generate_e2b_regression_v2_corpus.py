#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.dataset_forge.e2b_v2 import (
    E2BV2Paths,
    build_targets,
    generate,
    materialize,
    target_summary,
    verify_materialized,
    write_plan,
)
from router.dataset_forge.providers import ProviderError, provider_from_env


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Forge the sealed 2,000-task E2B regression V2 corpus.")
    parser.add_argument("--root", type=Path, default=Path("evals/e2b-regression-v2"))
    parser.add_argument("--config", type=Path, default=Path("configs/e2b-regression-v2-corpus.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/e2b-regression-v2-corpus.md"))
    parser.add_argument("--env-file", action="append", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--max-batches", type=int)
    parser.add_argument("--fireworks-budget-usd", type=float, default=5.0)
    parser.add_argument("--retry-target-ids-file", type=Path)
    args = parser.parse_args(argv)

    _load_env(tuple(args.env_file or (Path(".env.dataset-forge.local"), Path(".env.fireworks.local"))))
    root = _absolute(args.root)
    paths = E2BV2Paths(root)
    targets = build_targets()
    write_plan(paths, targets)
    output: dict[str, object] = {"plan": target_summary(targets), "executed": False}
    try:
        if args.execute:
            force_target_ids = _read_target_ids(args.retry_target_ids_file)
            providers = {
                name: provider_from_env(name, role="e2b_v2_generator", max_tokens=8192)
                for name in ("agy", "fireworks")
            }
            output["generation"] = generate(
                targets=targets,
                providers=providers,
                paths=paths,
                batch_size=args.batch_size,
                max_workers=args.max_workers,
                fireworks_budget_usd=args.fireworks_budget_usd,
                max_batches=args.max_batches,
                force_target_ids=force_target_ids,
            )
            output["executed"] = True
        if args.check:
            materialize(
                targets=targets,
                paths=paths,
                config_path=_absolute(args.config),
                report_path=_absolute(args.report),
            )
            output["verification"] = verify_materialized(_absolute(args.config))
    except (OSError, ProviderError, ValueError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


def _load_env(paths: tuple[Path, ...]) -> None:
    for relative in paths:
        path = _absolute(relative)
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip() and key.strip() not in os.environ:
                os.environ[key.strip()] = value.strip().strip('"').strip("'")


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _read_target_ids(path: Path | None) -> set[str]:
    if path is None:
        return set()
    resolved = _absolute(path)
    return {line.strip() for line in resolved.read_text(encoding="utf-8").splitlines() if line.strip()}


if __name__ == "__main__":
    raise SystemExit(main())
