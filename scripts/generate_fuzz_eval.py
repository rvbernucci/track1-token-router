#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.evals.fuzz_dataset import validate_fuzz_dataset, write_fuzz_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or validate the official-input fuzz pack.")
    parser.add_argument("--root", type=Path, default=Path("evals/fuzz"))
    parser.add_argument("--fixtures-root", type=Path, default=Path("fixtures/fuzz"))
    parser.add_argument("--check", action="store_true", help="Validate existing files instead of generating them.")
    args = parser.parse_args()

    if not args.check:
        write_fuzz_dataset(args.root, fixtures_root=args.fixtures_root)

    errors = validate_fuzz_dataset(args.root, fixtures_root=args.fixtures_root)
    if errors:
        for error in errors:
            print(f"fuzz dataset error: {error}", file=sys.stderr)
        return 1

    print(f"fuzz dataset ok: {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
