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
from router.core.policy import DEFAULT_POLICY
from router.evals.operational_envelope import TokenEnvelopeThresholds, build_token_envelope


def write_token_envelope_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    candidate = report["candidate"]
    lines = [
        "# Token Envelope Report",
        "",
        f"- ready: `{report['ready']}`",
        f"- candidate_policy: `{report['candidate_policy']}`",
        f"- candidate_run_exposure: `{candidate['run_exposure']}`",
        f"- candidate_max_task_exposure: `{candidate['max_task_exposure']}`",
        f"- thresholds: `{json.dumps(report['thresholds'], sort_keys=True)}`",
        f"- budget: `{json.dumps(report['budget'], sort_keys=True)}`",
        "",
        "## Policy Exposure",
        "",
        "| policy | remote_tasks | packet_tokens | remote_model_tokens | run_exposure | max_task_exposure | tasks_above_task_budget |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["policy_summaries"]:
        lines.append(
            "| "
            f"{row['policy']} | "
            f"{row['remote_tasks']} | "
            f"{row['packet_tokens_total']} | "
            f"{row['remote_model_tokens_total']} | "
            f"{row['run_exposure']} | "
            f"{row['max_task_exposure']} | "
            f"{row['tasks_above_task_budget']} |"
        )
    lines.extend(
        [
            "",
            "## Worst Case By Route",
            "",
            "| route | worst_task_exposure |",
            "|---|---:|",
        ]
    )
    for route, exposure in sorted(report["route_worst_case"].items()):
        lines.append(f"| {route} | {exposure} |")
    lines.extend(
        [
            "",
            "## Top 20 Expensive Tasks",
            "",
            "| policy | task_id | category | route | packet_tokens | remote_model_tokens | total_exposure |",
            "|---|---|---|---|---:|---:|---:|",
        ]
    )
    for row in report["top_tasks"]:
        lines.append(
            "| "
            f"{row['policy']} | "
            f"{row['task_id']} | "
            f"{row['category']} | "
            f"{row['route']} | "
            f"{row['packet_tokens']} | "
            f"{row['remote_model_tokens']} | "
            f"{row['total_exposure']} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `packet_tokens` estimates the compact remote audit prompt sent to Fireworks.",
            "- `remote_model_tokens` estimates provider-side completion usage from policy simulation.",
            "- `total_exposure` is conservative and intentionally treats both as spend pressure.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Estimate conservative remote token exposure by policy.")
    parser.add_argument("--jsonl", type=Path, default=Path("evals/offline/tasks.jsonl"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/token-envelope.md"))
    parser.add_argument("--candidate-policy", default=DEFAULT_POLICY)
    parser.add_argument("--check", action="store_true", help="Fail when candidate token envelope exceeds thresholds.")
    args = parser.parse_args()

    tasks = load_jsonl_tasks(args.jsonl)
    report = build_token_envelope(
        tasks,
        candidate_policy=args.candidate_policy,
        thresholds=TokenEnvelopeThresholds.from_env(),
    )
    write_token_envelope_report(args.report, report)
    print(json.dumps({"ok": report["ready"], "report": str(args.report), **report}, ensure_ascii=False, sort_keys=True))
    return 0 if report["ready"] or not args.check else 1


if __name__ == "__main__":
    raise SystemExit(main())
