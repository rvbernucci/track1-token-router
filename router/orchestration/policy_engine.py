from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from router.orchestration.budget import BudgetDecision
from router.orchestration.risk_signals import RiskSignalSet


@dataclass(frozen=True)
class PolicyThresholds:
    repair_threshold: int = 3
    remote_threshold: int = 5
    low_budget_deny_threshold: float = 0.05

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PolicyDecision:
    action: str
    reason: str
    risk_score: int
    reasons: list[str]
    thresholds: dict[str, object]

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "risk_score": self.risk_score,
            "reasons": self.reasons,
            "thresholds": self.thresholds,
        }


POLICY_PROFILES = {
    "adaptive_aggressive": PolicyThresholds(repair_threshold=4, remote_threshold=8, low_budget_deny_threshold=0.03),
    "adaptive_balanced": PolicyThresholds(repair_threshold=3, remote_threshold=5, low_budget_deny_threshold=0.05),
    "adaptive_conservative": PolicyThresholds(repair_threshold=2, remote_threshold=4, low_budget_deny_threshold=0.10),
}


def decide_policy(
    signals: RiskSignalSet,
    *,
    thresholds: PolicyThresholds | None = None,
    budget_decision: BudgetDecision | None = None,
) -> PolicyDecision:
    active = thresholds or PolicyThresholds()
    if budget_decision is not None and not budget_decision.allowed:
        return PolicyDecision(
            action="deny_remote",
            reason=budget_decision.decision,
            risk_score=signals.score,
            reasons=[*signals.reasons, budget_decision.reason],
            thresholds=active.to_dict(),
        )
    if signals.budget_remaining_ratio < active.low_budget_deny_threshold and signals.score >= active.remote_threshold:
        return PolicyDecision(
            action="deny_remote",
            reason="remote_too_expensive_for_remaining_budget",
            risk_score=signals.score,
            reasons=signals.reasons,
            thresholds=active.to_dict(),
        )
    if signals.unstable_knowledge:
        return PolicyDecision(
            action="remote_audit",
            reason="unstable_knowledge_requires_current_source",
            risk_score=signals.score,
            reasons=signals.reasons,
            thresholds=active.to_dict(),
        )
    if signals.answer_empty:
        return PolicyDecision(
            action="repair",
            reason="empty_answer_requires_local_repair",
            risk_score=signals.score,
            reasons=signals.reasons,
            thresholds=active.to_dict(),
        )
    if signals.complex_math or signals.prompt_injection:
        return PolicyDecision(
            action="repair",
            reason="local_repair_before_remote_spend",
            risk_score=signals.score,
            reasons=signals.reasons,
            thresholds=active.to_dict(),
        )
    if signals.score >= active.remote_threshold:
        return PolicyDecision(
            action="remote_audit",
            reason="risk_score_requires_remote_audit",
            risk_score=signals.score,
            reasons=signals.reasons,
            thresholds=active.to_dict(),
        )
    if signals.score >= active.repair_threshold and not _strict_format_only(signals):
        return PolicyDecision(
            action="repair",
            reason="risk_score_requires_local_repair",
            risk_score=signals.score,
            reasons=signals.reasons,
            thresholds=active.to_dict(),
        )
    return PolicyDecision(
        action="approve",
        reason="risk_within_local_acceptance",
        risk_score=signals.score,
        reasons=signals.reasons,
        thresholds=active.to_dict(),
    )


def _strict_format_only(signals: RiskSignalSet) -> bool:
    return signals.strict_format and set(signals.reasons).issubset({"strict_format"})


def decision_to_simulated_route(decision: PolicyDecision) -> str:
    if decision.action == "approve":
        return "m1_approved"
    if decision.action == "repair":
        return "m2b_candidate"
    if decision.action == "remote_audit":
        return "fireworks_replaced"
    return "m2b_candidate"
