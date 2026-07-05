from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from router.orchestration.budget import TaskBudget, summarize_policy_budget


@dataclass(frozen=True)
class ScoringWeights:
    accuracy: float = 1000.0
    remote_token: float = 0.02
    latency_ms: float = 0.001
    parse_failure: float = 25.0
    budget_violation: float = 50.0
    remote_packet_token: float = 0.001

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def build_scoreboard(
    comparison: dict[str, Any],
    weights: ScoringWeights,
    *,
    budget: TaskBudget | None = None,
    packet_tokens_by_policy: dict[str, int] | None = None,
) -> dict[str, Any]:
    rows = [
        _score_policy(
            policy,
            summary,
            weights,
            budget or TaskBudget(),
            (packet_tokens_by_policy or {}).get(policy, 0),
        )
        for policy, summary in comparison.get("policies", {}).items()
        if isinstance(summary, dict)
    ]
    rows.sort(key=lambda row: row["score"], reverse=True)
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return {
        "default_policy": comparison.get("default_policy"),
        "weights": weights.to_dict(),
        "formula": (
            "score = exact_match_rate * accuracy_weight "
            "- remote_tokens_total * remote_token_weight "
            "- latency_ms_total * latency_ms_weight "
            "- parse_failures * parse_failure_weight "
            "- budget_violations * budget_violation_weight "
            "- remote_packet_tokens * remote_packet_token_weight"
        ),
        "rows": rows,
    }


def write_scoreboard_json(path: Path, scoreboard: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scoreboard, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_scoreboard_report(path: Path, scoreboard: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    weights = scoreboard["weights"]
    lines = [
        "# Offline Scoreboard",
        "",
        f"- default_policy: `{scoreboard.get('default_policy')}`",
        f"- formula: `{scoreboard.get('formula')}`",
        (
            "- weights: "
            f"`accuracy={weights['accuracy']}`, "
            f"`remote_token={weights['remote_token']}`, "
            f"`latency_ms={weights['latency_ms']}`, "
            f"`parse_failure={weights['parse_failure']}`, "
            f"`budget_violation={weights['budget_violation']}`, "
            f"`remote_packet_token={weights['remote_packet_token']}`"
        ),
        "",
        "| rank | policy | score | exact_match_rate | remote_tokens | packet_tokens | budget_violations | latency_ms | parse_failures |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in scoreboard["rows"]:
        lines.append(
            "| "
            f"{row['rank']} | "
            f"{row['policy']} | "
            f"{row['score']:.3f} | "
            f"{row['exact_match_rate']:.3f} | "
            f"{row['remote_tokens_total']} | "
            f"{row.get('remote_packet_tokens', 0)} | "
            f"{row.get('budget_violations', 0)} | "
            f"{row['latency_ms_total']} | "
            f"{row['parse_failures']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Higher score is better.",
            "- Accuracy is rewarded heavily because the official score should not be won by cheap wrong answers.",
            "- Remote tokens, latency and parse failures are penalties because they can burn budget or break standardized scoring.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _score_policy(
    policy: str,
    summary: dict[str, Any],
    weights: ScoringWeights,
    budget: TaskBudget,
    remote_packet_tokens: int,
) -> dict[str, Any]:
    exact_match_rate = _float(summary.get("exact_match_rate"))
    remote_tokens_total = _int(_nested(summary, "remote_tokens", "total"))
    latency_ms_total = sum(_int(value) for value in (summary.get("latency_ms") or {}).values())
    parse_failures = _int(summary.get("parse_failures"))
    budget_summary = summarize_policy_budget(summary, budget)
    budget_violations = _int(budget_summary.get("budget_violations"))
    score = (
        exact_match_rate * weights.accuracy
        - remote_tokens_total * weights.remote_token
        - latency_ms_total * weights.latency_ms
        - parse_failures * weights.parse_failure
        - budget_violations * weights.budget_violation
        - remote_packet_tokens * weights.remote_packet_token
    )
    return {
        "rank": 0,
        "policy": policy,
        "score": round(score, 6),
        "exact_match_rate": exact_match_rate,
        "remote_tokens_total": remote_tokens_total,
        "remote_packet_tokens": remote_packet_tokens,
        "latency_ms_total": latency_ms_total,
        "parse_failures": parse_failures,
        "budget_violations": budget_violations,
        "budget": budget_summary,
        "escalation_rate": _float(summary.get("escalation_rate")),
        "replacement_rate": _float(summary.get("replacement_rate")),
        "expected_route_match_rate": _float(_nested(summary, "expected_route", "match_rate")),
        "routes": summary.get("routes", {}),
    }


def _nested(payload: dict[str, Any], first: str, second: str) -> Any:
    child = payload.get(first)
    if isinstance(child, dict):
        return child.get(second)
    return None


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
