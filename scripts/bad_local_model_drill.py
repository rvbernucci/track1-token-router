#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.evals.bad_local_model import (
    DEFAULT_TASKS_PATH,
    BadLocalModelThresholds,
    run_bad_local_model_drill,
    write_bad_local_model_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bad local model chaos drills without real model credits.")
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS_PATH)
    parser.add_argument("--report", type=Path, default=Path("reports/generated/bad-local-model-report.md"))
    parser.add_argument("--max-false-approval-rate", type=float, default=0.0)
    parser.add_argument("--min-containment-rate", type=float, default=1.0)
    parser.add_argument("--check", action="store_true", help="Fail if chaos gates are not met.")
    args = parser.parse_args()

    report = run_bad_local_model_drill(
        tasks_path=args.tasks,
        thresholds=BadLocalModelThresholds(
            max_false_approval_rate=args.max_false_approval_rate,
            min_containment_rate=args.min_containment_rate,
        ),
    )
    write_bad_local_model_report(args.report, report)
    print(json.dumps({"ok": report["ok"], "metrics": report["metrics"], "errors": report["errors"]}, sort_keys=True))
    return 0 if report["ok"] or not args.check else 1


if __name__ == "__main__":
    raise SystemExit(main())
