from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from router.core.contracts import TokenUsage


REMOTE_ROUTE_TOKEN_ESTIMATE = 280


@dataclass(frozen=True)
class TaskBudget:
    max_remote_tokens_per_task: int = 300
    max_remote_tokens_per_run: int = 6000
    max_remote_latency_ms: int = 3000
    parse_failure_penalty_tokens: int = 200

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class BudgetDecision:
    decision: str
    allowed: bool
    reason: str
    estimated_remote_tokens: int
    remaining_run_tokens: int
    latency_risk_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "allowed": self.allowed,
            "reason": self.reason,
            "estimated_remote_tokens": self.estimated_remote_tokens,
            "remaining_run_tokens": self.remaining_run_tokens,
            "latency_risk_ms": self.latency_risk_ms,
        }


class BudgetManager:
    def __init__(self, budget: TaskBudget | None = None) -> None:
        self.budget = budget or TaskBudget()
        self.remote_tokens_spent = 0
        self.remote_latency_ms = 0
        self.parse_failures = 0

    def allow_remote(self, *, estimated_remote_tokens: int, latency_risk_ms: int = 0) -> BudgetDecision:
        remaining = max(0, self.budget.max_remote_tokens_per_run - self.remote_tokens_spent)
        if estimated_remote_tokens > self.budget.max_remote_tokens_per_task:
            return BudgetDecision(
                decision="deny_remote_budget_exceeded",
                allowed=False,
                reason="estimated_remote_tokens_exceed_task_budget",
                estimated_remote_tokens=estimated_remote_tokens,
                remaining_run_tokens=remaining,
                latency_risk_ms=latency_risk_ms,
            )
        if estimated_remote_tokens > remaining:
            return BudgetDecision(
                decision="deny_remote_budget_exceeded",
                allowed=False,
                reason="estimated_remote_tokens_exceed_run_budget",
                estimated_remote_tokens=estimated_remote_tokens,
                remaining_run_tokens=remaining,
                latency_risk_ms=latency_risk_ms,
            )
        if latency_risk_ms > self.budget.max_remote_latency_ms:
            return BudgetDecision(
                decision="deny_remote_latency_risk",
                allowed=False,
                reason="estimated_latency_exceeds_remote_budget",
                estimated_remote_tokens=estimated_remote_tokens,
                remaining_run_tokens=remaining,
                latency_risk_ms=latency_risk_ms,
            )
        return BudgetDecision(
            decision="allow_remote",
            allowed=True,
            reason="within_budget",
            estimated_remote_tokens=estimated_remote_tokens,
            remaining_run_tokens=remaining,
            latency_risk_ms=latency_risk_ms,
        )

    def record_actual(self, usage: TokenUsage, *, latency_ms: int = 0, parse_failed: bool = False) -> None:
        penalty = self.budget.parse_failure_penalty_tokens if parse_failed else 0
        self.remote_tokens_spent += usage.total + penalty
        self.remote_latency_ms += latency_ms
        if parse_failed:
            self.parse_failures += 1

    def snapshot(self) -> dict[str, int]:
        return {
            "max_remote_tokens_per_task": self.budget.max_remote_tokens_per_task,
            "max_remote_tokens_per_run": self.budget.max_remote_tokens_per_run,
            "max_remote_latency_ms": self.budget.max_remote_latency_ms,
            "remote_tokens_spent": self.remote_tokens_spent,
            "remote_tokens_remaining": max(0, self.budget.max_remote_tokens_per_run - self.remote_tokens_spent),
            "remote_latency_ms": self.remote_latency_ms,
            "parse_failures": self.parse_failures,
        }


def estimate_remote_tokens_for_route(route: str) -> int:
    if route in {"fireworks_replaced", "m2b_fireworks_approved", "m2b_fireworks_error_approved"}:
        return REMOTE_ROUTE_TOKEN_ESTIMATE
    return 0


def summarize_policy_budget(summary: dict[str, Any], budget: TaskBudget | None = None) -> dict[str, Any]:
    active_budget = budget or TaskBudget()
    remote_tokens_total = _int((summary.get("remote_tokens") or {}).get("total"))
    parse_failures = _int(summary.get("parse_failures"))
    latency_ms_total = sum(_int(value) for value in (summary.get("latency_ms") or {}).values())
    task_budget_violations = 0
    run_budget_violations = 1 if remote_tokens_total > active_budget.max_remote_tokens_per_run else 0
    latency_violations = 1 if latency_ms_total > active_budget.max_remote_latency_ms else 0
    parse_failure_penalty_tokens = parse_failures * active_budget.parse_failure_penalty_tokens
    effective_spend = remote_tokens_total + parse_failure_penalty_tokens
    return {
        "budget": active_budget.to_dict(),
        "remote_tokens_total": remote_tokens_total,
        "parse_failure_penalty_tokens": parse_failure_penalty_tokens,
        "effective_remote_spend": effective_spend,
        "remaining_run_tokens": max(0, active_budget.max_remote_tokens_per_run - effective_spend),
        "task_budget_violations": task_budget_violations,
        "run_budget_violations": run_budget_violations,
        "latency_violations": latency_violations,
        "budget_violations": task_budget_violations + run_budget_violations + latency_violations,
    }


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
