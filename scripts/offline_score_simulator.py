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
from router.core.policy import POLICIES
from router.evals.policy_compare import compare_policies
from router.evals.scoring import (
    ScoringWeights,
    build_scoreboard,
    write_scoreboard_json,
    write_scoreboard_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an offline routing-policy scoreboard.")
    parser.add_argument("--jsonl", type=Path, default=Path("evals/offline/tasks.jsonl"))
    parser.add_argument("--expected", type=Path, default=Path("evals/offline/expected.jsonl"))
    parser.add_argument("--out-json", type=Path, default=Path("reports/generated/offline-scoreboard.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/offline-scoreboard.md"))
    parser.add_argument("--policies", nargs="+", default=list(POLICIES), choices=POLICIES)
    parser.add_argument("--accuracy-weight", type=float, default=1000.0)
    parser.add_argument("--remote-token-weight", type=float, default=0.02)
    parser.add_argument("--latency-ms-weight", type=float, default=0.001)
    parser.add_argument("--parse-failure-weight", type=float, default=25.0)
    parser.add_argument("--budget-violation-weight", type=float, default=50.0)
    parser.add_argument("--remote-packet-token-weight", type=float, default=0.001)
    parser.add_argument("--max-remote-tokens-per-task", type=int, default=300)
    parser.add_argument("--max-remote-tokens-per-run", type=int, default=6000)
    parser.add_argument("--max-remote-latency-ms", type=int, default=3000)
    args = parser.parse_args()

    weights = ScoringWeights(
        accuracy=args.accuracy_weight,
        remote_token=args.remote_token_weight,
        latency_ms=args.latency_ms_weight,
        parse_failure=args.parse_failure_weight,
        budget_violation=args.budget_violation_weight,
        remote_packet_token=args.remote_packet_token_weight,
    )
    from router.orchestration.budget import TaskBudget
    from router.orchestration.prompt_packet import estimate_policy_packet_tokens

    budget = TaskBudget(
        max_remote_tokens_per_task=args.max_remote_tokens_per_task,
        max_remote_tokens_per_run=args.max_remote_tokens_per_run,
        max_remote_latency_ms=args.max_remote_latency_ms,
    )
    tasks = load_jsonl_tasks(args.jsonl)
    comparison = compare_policies(tasks, args.expected, policies=tuple(args.policies))
    packet_tokens_by_policy = {
        policy: estimate_policy_packet_tokens(tasks, policy)
        for policy in args.policies
    }
    scoreboard = build_scoreboard(
        comparison,
        weights,
        budget=budget,
        packet_tokens_by_policy=packet_tokens_by_policy,
    )
    write_scoreboard_json(args.out_json, scoreboard)
    write_scoreboard_report(args.report, scoreboard)
    print(json.dumps(scoreboard["rows"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
