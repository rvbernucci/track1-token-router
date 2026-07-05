#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.evals.fuzz_dataset import run_fuzz_pack, validate_fuzz_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the no-credit fuzz eval through competition mode.")
    parser.add_argument("--root", type=Path, default=Path("evals/fuzz"))
    parser.add_argument("--fixtures-root", type=Path, default=Path("fixtures/fuzz"))
    parser.add_argument("--out", type=Path, default=Path("reports/generated/fuzz-output.jsonl"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/fuzz-report.md"))
    parser.add_argument("--check", action="store_true", help="Fail if the fuzz pack contract is not clean.")
    args = parser.parse_args()

    errors = validate_fuzz_dataset(args.root, fixtures_root=args.fixtures_root)
    if errors:
        for error in errors:
            print(f"fuzz dataset error: {error}", file=sys.stderr)
        return 1

    summary = run_fuzz_pack(root=args.root, out_path=args.out, report_path=args.report)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if args.check and not summary.get("contract_success"):
        print("fuzz eval error: contract_success=false", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
