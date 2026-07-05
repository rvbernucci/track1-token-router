from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from router.cli.main import _build_eval_summary, _load_expected_answers
from router.core.contracts import AnswerResult, TaskEnvelope
from router.core.policy import POLICIES, DEFAULT_POLICY, simulate_policy_route, simulated_remote_tokens


def compare_policies(
    tasks: list[TaskEnvelope],
    expected_path: Path,
    policies: tuple[str, ...] = POLICIES,
) -> dict[str, Any]:
    expected_by_id = _load_expected_answers(expected_path)
    comparisons: dict[str, Any] = {}
    for policy in policies:
        results = [_simulate_result(task, expected_by_id, policy) for task in tasks]
        comparisons[policy] = _build_eval_summary(tasks, results, expected_path)

    return {
        "default_policy": DEFAULT_POLICY,
        "policies": comparisons,
        "pareto": _pareto_rows(comparisons),
    }


def write_policy_report(path: Path, comparison: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Routing Policy Comparison",
        "",
        f"- default_policy: `{comparison['default_policy']}`",
        "",
        "| policy | exact_match_rate | escalation_rate | replacement_rate | remote_tokens | expected_route_match |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in comparison["pareto"]:
        lines.append(
            "| "
            f"{row['policy']} | "
            f"{row['exact_match_rate']} | "
            f"{row['escalation_rate']} | "
            f"{row['replacement_rate']} | "
            f"{row['remote_tokens_total']} | "
            f"{row['expected_route_match_rate']} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `aggressive` protects token budget but accepts more local risk.",
            "- `balanced` is the temporary default because it matches the offline expected route best.",
            "- `conservative` spends more simulated remote tokens to reduce difficult-task risk.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_policy_json(path: Path, comparison: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _simulate_result(task: TaskEnvelope, expected_by_id: dict[str, str], policy: str) -> AnswerResult:
    route = simulate_policy_route(task, policy)
    expected_answer = expected_by_id.get(task.id or "", "")
    answer = _simulated_answer(task, route, expected_answer)
    return AnswerResult(
        id=task.id,
        answer=answer,
        route=route,
        remote_tokens=simulated_remote_tokens(route),
        metadata={
            "runner": "policy_simulator",
            "policy": policy,
            "simulated": True,
        },
    )


def _simulated_answer(task: TaskEnvelope, route: str, expected_answer: str) -> str:
    expected_route = str(task.metadata.get("expected_route") or "")
    if route == expected_route:
        return expected_answer
    if route == "fireworks_replaced":
        return expected_answer
    if expected_route == "m1_approved" and route == "m2b_candidate":
        return expected_answer
    return f"SIMULATED_MISS[{route}]"


def _pareto_rows(comparisons: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for policy, summary in comparisons.items():
        rows.append(
            {
                "policy": policy,
                "exact_match_rate": summary.get("exact_match_rate", 0.0),
                "escalation_rate": summary.get("escalation_rate", 0.0),
                "replacement_rate": summary.get("replacement_rate", 0.0),
                "remote_tokens_total": summary.get("remote_tokens", {}).get("total", 0),
                "expected_route_match_rate": summary.get("expected_route", {}).get("match_rate", 0.0),
            }
        )
    return sorted(rows, key=lambda row: (row["remote_tokens_total"], -row["exact_match_rate"]))
