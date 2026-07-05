#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.analytics.traces import (
    expand_log_paths,
    load_trace_records,
    summarize_traces,
    write_trace_summary_json,
    write_trace_summary_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize router JSONL traces.")
    parser.add_argument("--logs", nargs="*", default=["logs/*.jsonl"], help="Log files or glob patterns.")
    parser.add_argument("--out-json", type=Path, default=Path("reports/generated/trace-summary.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/trace-summary.md"))
    args = parser.parse_args()

    paths = expand_log_paths(args.logs)
    records, errors = load_trace_records(paths)
    summary = summarize_traces(records, source_files=paths, ingestion_errors=errors)
    write_trace_summary_json(args.out_json, summary)
    write_trace_summary_report(args.report, summary)
    print(json.dumps({"records": summary["records"], "routes": summary["routes"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
