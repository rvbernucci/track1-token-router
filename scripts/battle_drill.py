#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.evals.battle_drill import run_battle_drill, write_battle_report_json, write_battle_report_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the offline competitive battle drill.")
    parser.add_argument("--jsonl", type=Path, default=Path("evals/offline/tasks.jsonl"))
    parser.add_argument("--expected", type=Path, default=Path("evals/offline/expected.jsonl"))
    parser.add_argument("--prompt-manifest", type=Path, default=Path("prompts/manifest.json"))
    parser.add_argument("--logs", nargs="*", default=["fixtures/logs/sample-run.jsonl"])
    parser.add_argument("--out-json", type=Path, default=Path("reports/generated/battle-report.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/battle-report.md"))
    args = parser.parse_args()

    report = run_battle_drill(
        tasks_path=args.jsonl,
        expected_path=args.expected,
        prompt_manifest=args.prompt_manifest,
        trace_logs=args.logs,
    )
    write_battle_report_json(args.out_json, report)
    write_battle_report_markdown(args.report, report)
    print(json.dumps({"candidate": report["candidate"].get("policy"), "readiness": report["readiness"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
