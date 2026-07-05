#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.adapters.io import load_jsonl_tasks
from router.cli.main import _load_expected_answers
from router.core.contracts import TaskEnvelope
from router.evals.scoring import ScoringWeights
from router.orchestration.budget import TaskBudget
from router.orchestration.policy_engine import PolicyThresholds, decide_policy, decision_to_simulated_route
from router.orchestration.prompt_packet import REMOTE_AUDIT_ROUTES, build_remote_audit_packet
from router.orchestration.risk_signals import extract_risk_signals


LOW_BUDGET_SWEEP = (0.03, 0.05, 0.10, 0.20)
DEFAULT_THRESHOLDS = PolicyThresholds()


@dataclass(frozen=True)
class OptimizationGrid:
    repair_thresholds: tuple[int, ...] = (1, 2, 3, 4, 5)
    remote_thresholds: tuple[int, ...] = (3, 4, 5, 6, 7, 8)
    low_budget_thresholds: tuple[float, ...] = LOW_BUDGET_SWEEP


def run_policy_optimization(
    *,
    tasks: list[TaskEnvelope],
    expected_path: Path,
    grid: OptimizationGrid | None = None,
    budget: TaskBudget | None = None,
    weights: ScoringWeights | None = None,
) -> dict[str, Any]:
    active_grid = grid or OptimizationGrid()
    active_budget = budget or TaskBudget()
    active_weights = weights or ScoringWeights()
    expected = _load_expected_answers(expected_path)
    rows = []
    for repair_threshold in active_grid.repair_thresholds:
        for remote_threshold in active_grid.remote_thresholds:
            if remote_threshold < repair_threshold:
                continue
            for low_budget in active_grid.low_budget_thresholds:
                thresholds = PolicyThresholds(
                    repair_threshold=repair_threshold,
                    remote_threshold=remote_threshold,
                    low_budget_deny_threshold=low_budget,
                )
                rows.append(_score_thresholds(tasks, expected, thresholds, active_budget, active_weights))
    _mark_dominated(rows)
    _mark_duplicate_surfaces(rows)
    rows.sort(
        key=lambda row: (
            row["dominated"],
            -row["exact_match_rate"],
            row["run_exposure"],
            row["escalation_rate"],
            -row["score"],
        )
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    first_candidate = next((row for row in rows if not row["dominated"]), rows[0] if rows else {})
    default_candidate = next((row for row in rows if _is_default_profile(row) and not row["dominated"]), None)
    recommended = default_candidate or first_candidate
    if recommended:
        recommended["recommendation_reason"] = (
            "current default is on the best observed Pareto surface"
            if default_candidate
            else "best non-dominated profile by accuracy, exposure and escalation"
        )
    return {
        "recommended": recommended,
        "rows": rows,
        "grid": {
            "repair_thresholds": list(active_grid.repair_thresholds),
            "remote_thresholds": list(active_grid.remote_thresholds),
            "low_budget_thresholds": list(active_grid.low_budget_thresholds),
        },
        "weights": active_weights.to_dict(),
        "budget": active_budget.to_dict(),
        "dominated": sum(1 for row in rows if row["dominated"]),
        "candidates": sum(1 for row in rows if not row["dominated"]),
    }


def write_policy_pareto_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    recommended = report.get("recommended") or {}
    lines = [
        "# Policy Pareto Report",
        "",
        f"- recommended_profile: `{recommended.get('profile')}`",
        f"- recommended_reason: `{recommended.get('recommendation_reason')}`",
        f"- candidates: `{report.get('candidates')}`",
        f"- dominated: `{report.get('dominated')}`",
        f"- weights: `{json.dumps(report.get('weights'), sort_keys=True)}`",
        "",
        "## Pareto Table",
        "",
        "| rank | profile | dominated | score | exact_match_rate | run_exposure | packet_tokens | escalation_rate | budget_violations | actions |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["rows"][:30]:
        lines.append(
            "| "
            f"{row['rank']} | "
            f"{row['profile']} | "
            f"{row['dominated']} | "
            f"{row['score']:.3f} | "
            f"{row['exact_match_rate']:.3f} | "
            f"{row['run_exposure']} | "
            f"{row['packet_tokens']} | "
            f"{row['escalation_rate']:.3f} | "
            f"{row['budget_violations']} | "
            f"`{json.dumps(row['actions'], sort_keys=True)}` |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- A dominated profile is no better on accuracy and no cheaper on exposure/escalation than another profile.",
            "- `run_exposure` is conservative: remote model tokens plus compact audit packet tokens.",
            "- The optimizer is a decision aid. Final policy should still consider official scoring, latency and evaluator format.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Explore Pareto frontier for adaptive routing thresholds.")
    parser.add_argument("--jsonl", type=Path, default=Path("evals/offline/tasks.jsonl"))
    parser.add_argument("--expected", type=Path, default=Path("evals/offline/expected.jsonl"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/policy-pareto.md"))
    parser.add_argument("--check", action="store_true", help="Fail if no non-dominated profile is found.")
    args = parser.parse_args()

    tasks = load_jsonl_tasks(args.jsonl)
    report = run_policy_optimization(tasks=tasks, expected_path=args.expected)
    write_policy_pareto_report(args.report, report)
    payload = {
        "ok": bool(report.get("recommended")),
        "recommended": (report.get("recommended") or {}).get("profile"),
        "candidates": report.get("candidates"),
        "dominated": report.get("dominated"),
        "report": str(args.report),
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["ok"] or not args.check else 1


def _score_thresholds(
    tasks: list[TaskEnvelope],
    expected: dict[str, str],
    thresholds: PolicyThresholds,
    budget: TaskBudget,
    weights: ScoringWeights,
) -> dict[str, Any]:
    exact = 0
    packet_tokens = 0
    remote_model_tokens = 0
    actions: dict[str, int] = {}
    routes: dict[str, int] = {}
    run_exposure = 0
    max_task_exposure = 0
    for task in tasks:
        signals = extract_risk_signals(task)
        decision = decide_policy(signals, thresholds=thresholds)
        route = decision_to_simulated_route(decision)
        actions[decision.action] = actions.get(decision.action, 0) + 1
        routes[route] = routes.get(route, 0) + 1
        model_tokens = 280 if route in REMOTE_AUDIT_ROUTES else 0
        audit_packet_tokens = _packet_tokens(task, route)
        total_exposure = model_tokens + audit_packet_tokens
        packet_tokens += audit_packet_tokens
        remote_model_tokens += model_tokens
        run_exposure += total_exposure
        max_task_exposure = max(max_task_exposure, total_exposure)
        if _proxy_exact_match(task, route, expected):
            exact += 1
    tasks_count = len(tasks)
    exact_match_rate = exact / tasks_count if tasks_count else 0.0
    escalation_count = actions.get("repair", 0) + actions.get("remote_audit", 0)
    budget_violations = int(remote_model_tokens > budget.max_remote_tokens_per_run)
    score = (
        exact_match_rate * weights.accuracy
        - remote_model_tokens * weights.remote_token
        - packet_tokens * weights.remote_packet_token
        - budget_violations * weights.budget_violation
    )
    profile = (
        f"repair={thresholds.repair_threshold};"
        f"remote={thresholds.remote_threshold};"
        f"low_budget={thresholds.low_budget_deny_threshold:.2f}"
    )
    return {
        "rank": 0,
        "profile": profile,
        "thresholds": thresholds.to_dict(),
        "score": round(score, 6),
        "exact_match_rate": exact_match_rate,
        "exact_matches": exact,
        "tasks": tasks_count,
        "packet_tokens": packet_tokens,
        "remote_model_tokens": remote_model_tokens,
        "run_exposure": run_exposure,
        "max_task_exposure": max_task_exposure,
        "escalation_rate": escalation_count / tasks_count if tasks_count else 0.0,
        "budget_violations": budget_violations,
        "actions": actions,
        "routes": routes,
        "dominated": False,
        "recommendation_reason": "best non-dominated profile by accuracy, exposure and escalation",
    }


def _packet_tokens(task: TaskEnvelope, route: str) -> int:
    if route not in REMOTE_AUDIT_ROUTES:
        return 0
    packet = build_remote_audit_packet(
        task,
        candidate="LOCAL_CANDIDATE",
        concern=str(task.metadata.get("risk") or "routing_risk"),
    )
    return packet.approx_tokens()


def _proxy_exact_match(task: TaskEnvelope, route: str, expected: dict[str, str]) -> bool:
    if task.id not in expected:
        return False
    expected_route = str(task.metadata.get("expected_route") or "")
    if route == expected_route:
        return True
    if route == "fireworks_replaced":
        return True
    if expected_route == "m1_approved" and route == "m2b_candidate":
        return True
    return False


def _mark_dominated(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        row["dominated"] = any(_dominates(other, row) for other in rows if other is not row)


def _mark_duplicate_surfaces(rows: list[dict[str, Any]]) -> None:
    seen: dict[tuple[float, int, float, int], str] = {}
    for row in sorted(rows, key=lambda item: (not _is_default_profile(item), item["profile"])):
        key = (
            float(row["exact_match_rate"]),
            int(row["run_exposure"]),
            float(row["escalation_rate"]),
            int(row["budget_violations"]),
        )
        if key in seen:
            row["dominated"] = True
            row["dominated_by"] = seen[key]
        else:
            seen[key] = str(row["profile"])


def _dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    better_or_equal = (
        left["exact_match_rate"] >= right["exact_match_rate"]
        and left["run_exposure"] <= right["run_exposure"]
        and left["escalation_rate"] <= right["escalation_rate"]
        and left["budget_violations"] <= right["budget_violations"]
    )
    strictly_better = (
        left["exact_match_rate"] > right["exact_match_rate"]
        or left["run_exposure"] < right["run_exposure"]
        or left["escalation_rate"] < right["escalation_rate"]
        or left["budget_violations"] < right["budget_violations"]
    )
    return better_or_equal and strictly_better


def _is_default_profile(row: dict[str, Any]) -> bool:
    thresholds = row.get("thresholds") or {}
    return (
        thresholds.get("repair_threshold") == DEFAULT_THRESHOLDS.repair_threshold
        and thresholds.get("remote_threshold") == DEFAULT_THRESHOLDS.remote_threshold
        and thresholds.get("low_budget_deny_threshold") == DEFAULT_THRESHOLDS.low_budget_deny_threshold
    )


if __name__ == "__main__":
    raise SystemExit(main())
