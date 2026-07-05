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
from router.evals.policy_ablation import (
    run_policy_ablation,
    write_policy_ablation_json,
    write_policy_ablation_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run offline adaptive policy threshold ablation.")
    parser.add_argument("--jsonl", type=Path, default=Path("evals/offline/tasks.jsonl"))
    parser.add_argument("--out-json", type=Path, default=Path("reports/generated/policy-ablation.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/policy-ablation.md"))
    args = parser.parse_args()

    report = run_policy_ablation(load_jsonl_tasks(args.jsonl))
    write_policy_ablation_json(args.out_json, report)
    write_policy_ablation_report(args.report, report)
    print(json.dumps(report["profiles"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
