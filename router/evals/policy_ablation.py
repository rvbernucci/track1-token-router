from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from router.core.contracts import TaskEnvelope
from router.orchestration.policy_engine import POLICY_PROFILES, decide_policy, decision_to_simulated_route
from router.orchestration.risk_signals import extract_risk_signals


def run_policy_ablation(tasks: list[TaskEnvelope]) -> dict[str, Any]:
    rows = []
    for profile, thresholds in POLICY_PROFILES.items():
        matches = 0
        route_counts: dict[str, int] = {}
        actions: dict[str, int] = {}
        total_risk = 0
        for task in tasks:
            signals = extract_risk_signals(task)
            decision = decide_policy(signals, thresholds=thresholds)
            route = decision_to_simulated_route(decision)
            route_counts[route] = route_counts.get(route, 0) + 1
            actions[decision.action] = actions.get(decision.action, 0) + 1
            total_risk += signals.score
            if route == str(task.metadata.get("expected_route") or ""):
                matches += 1
        rows.append(
            {
                "profile": profile,
                "thresholds": thresholds.to_dict(),
                "tasks": len(tasks),
                "expected_route_matches": matches,
                "expected_route_match_rate": matches / len(tasks) if tasks else 0.0,
                "average_risk_score": total_risk / len(tasks) if tasks else 0.0,
                "routes": route_counts,
                "actions": actions,
            }
        )
    rows.sort(key=lambda row: (row["expected_route_match_rate"], -row["actions"].get("remote_audit", 0)), reverse=True)
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return {"profiles": rows}


def write_policy_ablation_json(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_policy_ablation_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Policy Ablation Report",
        "",
        "| rank | profile | expected_route_match_rate | average_risk_score | actions | routes |",
        "|---:|---|---:|---:|---|---|",
    ]
    for row in report["profiles"]:
        lines.append(
            "| "
            f"{row['rank']} | "
            f"{row['profile']} | "
            f"{row['expected_route_match_rate']:.3f} | "
            f"{row['average_risk_score']:.3f} | "
            f"`{json.dumps(row['actions'], sort_keys=True)}` | "
            f"`{json.dumps(row['routes'], sort_keys=True)}` |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Profiles are deterministic threshold sets, not model calls.",
            "- `remote_audit` is useful only when it buys expected-route accuracy worth the token cost.",
            "- This report is a calibration surface for changing thresholds without editing prompts.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
