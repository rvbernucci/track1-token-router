#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.evals.operational_envelope import LatencyThresholds, summarize_latency_envelope


SAMPLE_TASKS = [
    "What is 2 + 2? Return only the number.",
    "What is 6 * 7? Return only the number.",
    "Return exactly SAFE_OUTPUT and nothing else.",
    "Return compact JSON with ok=true and count=2.",
]


def run_latency_drill(*, thresholds: LatencyThresholds | None = None) -> dict[str, object]:
    active = thresholds or LatencyThresholds.from_env()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        samples = [
            _measure_cli_ask(task, log_path=tmp_root / f"ask-{index}.jsonl")
            for index, task in enumerate(SAMPLE_TASKS, start=1)
        ]
        batch_elapsed_ms = _measure_jsonl_batch(tmp_root)
    return summarize_latency_envelope(
        samples,
        batch_elapsed_ms=batch_elapsed_ms,
        batch_tasks=len(SAMPLE_TASKS),
        thresholds=active,
    )


def write_latency_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Latency Drill Report",
        "",
        f"- ready: `{report['ready']}`",
        f"- cold_start_ms: `{report['cold_start_ms']}`",
        f"- p50_ms: `{report['p50_ms']}`",
        f"- p95_ms: `{report['p95_ms']}`",
        f"- p99_ms: `{report['p99_ms']}`",
        f"- batch_elapsed_ms: `{report['batch_elapsed_ms']}`",
        f"- batch_tasks_per_second: `{report['batch_tasks_per_second']}`",
        f"- thresholds: `{json.dumps(report['thresholds'], sort_keys=True)}`",
        "",
        "## Samples",
        "",
        "| sample | elapsed_ms |",
        "|---:|---:|",
    ]
    for index, value in enumerate(report["samples_ms"], start=1):
        lines.append(f"| {index} | {value} |")
    lines.extend(
        [
            "",
            "## Timeout Probes",
            "",
            f"- local_timeout_probe: `{json.dumps(report['local_timeout_probe'], sort_keys=True)}`",
            f"- remote_timeout_probe: `{json.dumps(report['remote_timeout_probe'], sort_keys=True)}`",
            "",
            "## Notes",
            "",
            "- This is an offline dry-run benchmark. It measures CLI/container overhead and simulated timeout detection, not real AMD or Fireworks latency.",
            "- Thresholds are intentionally conservative and configurable with `LATENCY_DRILL_*` env vars.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure offline CLI latency and timeout envelope.")
    parser.add_argument("--report", type=Path, default=Path("reports/generated/latency-report.md"))
    parser.add_argument("--check", action="store_true", help="Fail when latency envelope is outside thresholds.")
    args = parser.parse_args()

    report = run_latency_drill()
    write_latency_report(args.report, report)
    print(json.dumps({"ok": report["ready"], "report": str(args.report), **report}, ensure_ascii=False, sort_keys=True))
    return 0 if report["ready"] or not args.check else 1


def _measure_cli_ask(task: str, *, log_path: Path) -> float:
    env = _competition_env(log_path)
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, "-m", "router", "ask", task, "--json"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    json.loads(completed.stdout)
    if completed.stderr.strip():
        raise RuntimeError(f"latency drill expected clean stderr, got: {completed.stderr.strip()}")
    return elapsed_ms


def _measure_jsonl_batch(tmp_root: Path) -> float:
    jsonl_path = tmp_root / "batch.jsonl"
    out_path = tmp_root / "batch.out.jsonl"
    rows = [
        {"id": f"latency-{index}", "input_text": task, "metadata": {"source": "latency_drill"}}
        for index, task in enumerate(SAMPLE_TASKS, start=1)
    ]
    jsonl_path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    env = _competition_env(tmp_root / "batch-run.jsonl")
    started = time.perf_counter()
    subprocess.run(
        [sys.executable, "-m", "router", "run", "--jsonl", str(jsonl_path), "--out", str(out_path)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    if len(out_path.read_text(encoding="utf-8").splitlines()) != len(SAMPLE_TASKS):
        raise RuntimeError("latency batch output count mismatch.")
    return elapsed_ms


def _competition_env(log_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["ROUTER_MODE"] = "competition"
    env["COMPETITION_DRY_RUN"] = "1"
    env["ROUTER_LOG_PATH"] = str(log_path)
    return env


if __name__ == "__main__":
    raise SystemExit(main())
