#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.core.contracts import TaskEnvelope
from router.core.mock_runner import MockCascadeRunner
from router.orchestration.competition import CompetitionRunner


def replay_decision(text: str, *, task_id: str | None = "replay") -> dict[str, Any]:
    task = TaskEnvelope(id=task_id, input_text=text)
    runner = CompetitionRunner(MockCascadeRunner(), dry_run=True)
    result = runner.run(task)
    trace = result.metadata["competition_trace"]
    decision = trace["decision"]
    return {
        "task": task.to_dict(),
        "answer": result.answer,
        "route": result.route,
        "candidate_route": result.metadata.get("candidate_route"),
        "decision": decision,
        "orchestration_trace": result.metadata.get("orchestration_trace"),
    }


def write_replay_report(path: Path, replay: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    decision = replay["decision"]
    lines = [
        "# Decision Replay",
        "",
        f"- task_id: `{replay['task'].get('id')}`",
        f"- input: {replay['task'].get('input_text')}",
        f"- final_route: `{replay['route']}`",
        f"- candidate_route: `{replay.get('candidate_route')}`",
        f"- final_answer: `{replay['answer']}`",
        f"- remote_would_call: `{decision.get('remote_would_call')}`",
        f"- remote_packet_tokens: `{decision.get('remote_packet_tokens')}`",
        "",
        "## Deterministic Path",
        "",
        _deterministic_summary(replay),
        "",
        "## Risk Signals",
        "",
        f"```json\n{json.dumps(decision.get('risk_signals'), indent=2, sort_keys=True)}\n```",
        "",
        "## Budget Decision",
        "",
        f"```json\n{json.dumps(decision.get('budget_decision'), indent=2, sort_keys=True)}\n```",
        "",
        "## Policy Decision",
        "",
        f"```json\n{json.dumps(decision.get('policy_decision'), indent=2, sort_keys=True)}\n```",
        "",
        "## Final Validator",
        "",
        f"```json\n{json.dumps(decision.get('final_validation'), indent=2, sort_keys=True)}\n```",
        "",
        "## State Trace",
        "",
        f"```json\n{json.dumps(replay.get('orchestration_trace'), indent=2, sort_keys=True)}\n```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay one competition-mode routing decision as Markdown.")
    parser.add_argument("--text", required=True)
    parser.add_argument("--id", dest="task_id", default="replay")
    parser.add_argument("--report", type=Path, default=Path("reports/generated/decision-replay.md"))
    args = parser.parse_args()

    replay = replay_decision(args.text, task_id=args.task_id)
    write_replay_report(args.report, replay)
    print(json.dumps({"route": replay["route"], "answer": replay["answer"], "report": str(args.report)}, sort_keys=True))
    return 0


def _deterministic_summary(replay: dict[str, Any]) -> str:
    route = str(replay.get("route") or "")
    if route.startswith("guardrail_"):
        return f"- Guardrail answered before model routing: `{route}`."
    if route.startswith("solver_"):
        return f"- Deterministic solver answered before model routing: `{route}`."
    return "- No deterministic guardrail or solver answered; the request continued into local candidate verification."


if __name__ == "__main__":
    raise SystemExit(main())
