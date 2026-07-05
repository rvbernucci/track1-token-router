#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.adapters.io import load_jsonl_tasks
from router.core.policy import POLICIES
from router.evals.policy_compare import compare_policies, write_policy_json, write_policy_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare routing policies offline.")
    parser.add_argument("--jsonl", type=Path, default=Path("evals/offline/tasks.jsonl"))
    parser.add_argument("--expected", type=Path, default=Path("evals/offline/expected.jsonl"))
    parser.add_argument("--out-json", type=Path, default=Path("reports/generated/policy-comparison.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/policy-comparison.md"))
    parser.add_argument("--policies", nargs="+", default=list(POLICIES), choices=POLICIES)
    args = parser.parse_args()

    tasks = load_jsonl_tasks(args.jsonl)
    comparison = compare_policies(tasks, args.expected, policies=tuple(args.policies))
    write_policy_json(args.out_json, comparison)
    write_policy_report(args.report, comparison)
    print(json.dumps(comparison["pareto"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
