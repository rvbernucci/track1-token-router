#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.evals.semantic_judge import (
    DEFAULT_RUBRICS_PATH,
    DEFAULT_TASKS_PATH,
    run_semantic_eval,
    write_semantic_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic semantic eval rubrics.")
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS_PATH)
    parser.add_argument("--rubrics", type=Path, default=DEFAULT_RUBRICS_PATH)
    parser.add_argument("--answers", type=Path)
    parser.add_argument("--report", type=Path, default=Path("reports/generated/semantic-eval.md"))
    parser.add_argument("--check", action="store_true", help="Fail if semantic rubric validation fails.")
    args = parser.parse_args()

    report = run_semantic_eval(tasks_path=args.tasks, rubrics_path=args.rubrics, answers_path=args.answers)
    write_semantic_report(args.report, report)
    print(json.dumps({"ok": report["ok"], "metrics": report["metrics"], "errors": report["errors"]}, sort_keys=True))
    return 0 if report["ok"] or not args.check else 1


if __name__ == "__main__":
    raise SystemExit(main())
