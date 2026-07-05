#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.evals.offline_dataset import validate_offline_dataset, write_offline_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or validate the offline eval arena.")
    parser.add_argument("--root", type=Path, default=Path("evals/offline"))
    parser.add_argument("--per-category", type=int, default=20)
    parser.add_argument("--check", action="store_true", help="Validate existing files instead of generating them.")
    args = parser.parse_args()

    if not args.check:
        write_offline_dataset(args.root, per_category=args.per_category)

    errors = validate_offline_dataset(args.root)
    if errors:
        for error in errors:
            print(f"offline dataset error: {error}", file=sys.stderr)
        return 1

    print(f"offline dataset ok: {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
