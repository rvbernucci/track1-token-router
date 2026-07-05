#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RehearsalStep:
    name: str
    command: list[str]
    narration_seconds: int
    env: dict[str, str] | None = None


STEPS = [
    RehearsalStep(
        name="CLI deterministic answer",
        command=[sys.executable, "-m", "router", "ask", "What is 6 * 7? Return only the number.", "--json"],
        narration_seconds=25,
        env={"ROUTER_MODE": "competition", "COMPETITION_DRY_RUN": "1"},
    ),
    RehearsalStep(
        name="Decision replay",
        command=[
            sys.executable,
            "scripts/replay_decision.py",
            "--text",
            "Who is the CEO of AMD today?",
            "--report",
            "reports/generated/rehearsal-decision-replay.md",
        ],
        narration_seconds=45,
    ),
    RehearsalStep(
        name="Demo site check",
        command=[sys.executable, "scripts/check_demo_site.py", "--check"],
        narration_seconds=30,
    ),
    RehearsalStep(
        name="Log redaction check",
        command=[sys.executable, "scripts/redact_logs.py", "--check"],
        narration_seconds=35,
    ),
    RehearsalStep(
        name="Strict submission readiness",
        command=[sys.executable, "scripts/submission_readiness_check.py", "--strict"],
        narration_seconds=40,
    ),
]


def run_submission_rehearsal(*, report_path: Path = Path("reports/generated/submission-rehearsal.md")) -> dict[str, Any]:
    rows = []
    command_elapsed_seconds = 0.0
    errors = []
    for step in STEPS:
        env = os.environ.copy()
        if step.env:
            env.update(step.env)
        started = time.perf_counter()
        completed = subprocess.run(step.command, capture_output=True, text=True, env=env)
        elapsed = time.perf_counter() - started
        command_elapsed_seconds += elapsed
        ok = completed.returncode == 0
        if not ok:
            errors.append(f"{step.name}: command failed with exit {completed.returncode}")
        rows.append(
            {
                "name": step.name,
                "command": " ".join(step.command),
                "returncode": completed.returncode,
                "elapsed_seconds": round(elapsed, 3),
                "narration_seconds": step.narration_seconds,
                "stdout_preview": _preview(completed.stdout),
                "stderr_preview": _preview(completed.stderr),
            }
        )
    narration_seconds = sum(step.narration_seconds for step in STEPS)
    estimated_video_seconds = round(narration_seconds + command_elapsed_seconds, 3)
    checklist = {
        "audio_check_planned": True,
        "screen_resolution_check_planned": True,
        "terminal_font_check_planned": True,
        "runbook_exists": Path("docs/SUBMISSION_REHEARSAL.md").exists(),
        "redaction_report_generated": Path("reports/generated/redaction-report.md").exists(),
    }
    if estimated_video_seconds > 300:
        errors.append("estimated rehearsal exceeds 5 minutes")
    if not all(checklist.values()):
        errors.append("rehearsal checklist is incomplete")
    result = {
        "ok": not errors,
        "steps": rows,
        "command_elapsed_seconds": round(command_elapsed_seconds, 3),
        "narration_seconds": narration_seconds,
        "estimated_video_seconds": estimated_video_seconds,
        "checklist": checklist,
        "errors": errors,
    }
    write_rehearsal_report(report_path, result)
    return result


def write_rehearsal_report(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Submission Rehearsal Report",
        "",
        f"- ok: `{result['ok']}`",
        f"- command_elapsed_seconds: `{result['command_elapsed_seconds']}`",
        f"- narration_seconds: `{result['narration_seconds']}`",
        f"- estimated_video_seconds: `{result['estimated_video_seconds']}`",
        "",
        "## Steps",
        "",
        "| step | returncode | elapsed_seconds | narration_seconds |",
        "|---|---:|---:|---:|",
    ]
    for step in result["steps"]:
        lines.append(
            "| "
            f"{step['name']} | "
            f"{step['returncode']} | "
            f"{step['elapsed_seconds']} | "
            f"{step['narration_seconds']} |"
        )
    lines.extend(["", "## Capture Checklist", ""])
    for key, value in result["checklist"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Errors", ""])
    lines.extend([f"- {error}" for error in result["errors"]] or ["- none"])
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the final submission rehearsal command sequence.")
    parser.add_argument("--report", type=Path, default=Path("reports/generated/submission-rehearsal.md"))
    parser.add_argument("--check", action="store_true", help="Fail if rehearsal is not ready.")
    args = parser.parse_args()

    result = run_submission_rehearsal(report_path=args.report)
    print(
        json.dumps(
            {
                "ok": result["ok"],
                "estimated_video_seconds": result["estimated_video_seconds"],
                "errors": result["errors"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["ok"] or not args.check else 1


def _preview(value: str, max_chars: int = 240) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


if __name__ == "__main__":
    raise SystemExit(main())
