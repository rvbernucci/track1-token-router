#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.core.contracts import AnswerResult, TaskEnvelope
from router.orchestration.state_machine import (
    build_orchestration_trace,
    write_state_machine_json,
    write_state_machine_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a local state-machine report from canonical routes.")
    parser.add_argument("--out-json", type=Path, default=Path("reports/generated/state-machine-report.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/state-machine-report.md"))
    args = parser.parse_args()

    task = TaskEnvelope(id="state-demo", input_text="demo")
    routes = [
        "guardrail_arithmetic",
        "m1_approved",
        "m2b_candidate",
        "m2b_fireworks_approved",
        "fireworks_replaced",
        "m2b_fireworks_error_approved",
        "m2b_error_return_m1",
        "local_error",
    ]
    traces = [
        build_orchestration_trace(
            task,
            AnswerResult(
                id=task.id,
                answer="demo",
                route=route,
                metadata={"fireworks_parse_failed": route == "fireworks_replaced"},
            ),
            guardrail_reason="demo_guardrail" if route.startswith("guardrail_") else "",
        )
        for route in routes
    ]
    write_state_machine_json(args.out_json, traces)
    write_state_machine_report(args.report, traces)
    print(str(args.report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
