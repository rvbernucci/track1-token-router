#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.adapters.official import get_adapter
from router.core.contracts import AnswerResult


DRILLS = {
    "lablab_track1": Path("fixtures/official/lablab_track1_tasks.json"),
    "scoring_text_batch": Path("fixtures/adapter-drill/scoring_text_batch.txt"),
    "scoring_json_envelope": Path("fixtures/adapter-drill/scoring_json_envelope.json"),
    "scoring_file_bundle": Path("fixtures/adapter-drill/scoring_file_bundle.json"),
}
TARGET_ADAPTER_MINUTES = 30.0


@dataclass(frozen=True)
class DrillResult:
    adapter: str
    fixture: str
    tasks: int
    output_chars: int
    elapsed_ms: float
    ok: bool
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "adapter": self.adapter,
            "fixture": self.fixture,
            "tasks": self.tasks,
            "output_chars": self.output_chars,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "ok": self.ok,
            "error": self.error,
        }


def run_adapter_drill(*, fixture_root: Path = Path(".")) -> list[DrillResult]:
    results: list[DrillResult] = []
    for adapter_name, fixture_path in DRILLS.items():
        full_fixture_path = fixture_root / fixture_path
        started = time.perf_counter()
        try:
            raw = full_fixture_path.read_text(encoding="utf-8")
            adapter = get_adapter(adapter_name)
            tasks = adapter.parse(raw)
            answers = [
                AnswerResult(
                    id=task.id,
                    answer=_fixture_answer(task.id, index),
                    route="adapter_drill",
                    metadata={"adapter": adapter_name},
                )
                for index, task in enumerate(tasks, start=1)
            ]
            output = adapter.format(answers)
            _validate_output(adapter_name, output, tasks_count=len(tasks))
            elapsed_ms = (time.perf_counter() - started) * 1000
            results.append(
                DrillResult(
                    adapter=adapter_name,
                    fixture=str(fixture_path),
                    tasks=len(tasks),
                    output_chars=len(output),
                    elapsed_ms=elapsed_ms,
                    ok=True,
                )
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            results.append(
                DrillResult(
                    adapter=adapter_name,
                    fixture=str(fixture_path),
                    tasks=0,
                    output_chars=0,
                    elapsed_ms=elapsed_ms,
                    ok=False,
                    error=str(exc),
                )
            )
    return results


def write_report(results: list[DrillResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Adapter Drill Report",
        "",
        f"- target_adapter_minutes: `{TARGET_ADAPTER_MINUTES}`",
        f"- adapters: `{len(results)}`",
        f"- ok: `{all(result.ok for result in results)}`",
        "",
        "| adapter | fixture | tasks | output_chars | elapsed_ms | ok |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for result in results:
        lines.append(
            "| {adapter} | {fixture} | {tasks} | {output_chars} | {elapsed_ms:.3f} | {ok} |".format(
                adapter=result.adapter,
                fixture=result.fixture,
                tasks=result.tasks,
                output_chars=result.output_chars,
                elapsed_ms=result.elapsed_ms,
                ok=result.ok,
            )
        )
    lines.extend(
        [
            "",
            "## Kickoff Decision Rule",
            "",
            "If the official evaluator contract differs, add or update only one adapter, one fixture and one round-trip test first. Do not edit `router/core/*` unless the task model itself cannot represent the official contract.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run simulated evaluator adapter drills.")
    parser.add_argument("--report", type=Path, default=Path("reports/generated/adapter-drill-report.md"))
    parser.add_argument("--fixture-root", type=Path, default=Path("."))
    parser.add_argument("--check", action="store_true", help="Fail when any adapter drill fails.")
    args = parser.parse_args()

    results = run_adapter_drill(fixture_root=args.fixture_root)
    write_report(results, args.report)
    payload = {
        "ok": all(result.ok for result in results),
        "target_adapter_minutes": TARGET_ADAPTER_MINUTES,
        "results": [result.to_dict() for result in results],
        "report": str(args.report),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] or not args.check else 1


def _fixture_answer(task_id: str | None, index: int) -> str:
    return f"DRILL_OK:{task_id or index}"


def _validate_output(adapter_name: str, output: str, *, tasks_count: int) -> None:
    if not output.strip():
        raise ValueError(f"{adapter_name} produced empty output.")
    if adapter_name == "scoring_json_envelope":
        payload = json.loads(output)
        answers = payload.get("answers") if isinstance(payload, dict) else None
        if not isinstance(answers, list) or len(answers) != tasks_count:
            raise ValueError("scoring_json_envelope output must contain one answer per task.")
    if adapter_name == "lablab_track1":
        payload = json.loads(output)
        if not isinstance(payload, list) or len(payload) != tasks_count:
            raise ValueError("lablab_track1 output must contain one result per task.")
        for row in payload:
            if not isinstance(row, dict) or not row.get("task_id") or "answer" not in row:
                raise ValueError("lablab_track1 rows must contain task_id and answer.")
    if adapter_name == "scoring_text_batch" and len(output.splitlines()) != tasks_count:
        raise ValueError("scoring_text_batch output must contain one line per task.")


if __name__ == "__main__":
    raise SystemExit(main())
