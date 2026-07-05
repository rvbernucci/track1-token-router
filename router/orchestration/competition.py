from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from router.core.contracts import AnswerResult, TaskEnvelope, TokenUsage
from router.core.guardrails import GuardrailDecision, evaluate_guardrail
from router.core.logging import JsonlRunLogger
from router.core.runner import TaskRunner
from router.orchestration.budget import BudgetDecision, BudgetManager, TaskBudget
from router.orchestration.final_validator import FinalValidationResult, validate_final_answer
from router.orchestration.policy_engine import POLICY_PROFILES, PolicyDecision, decide_policy
from router.orchestration.prompt_packet import RemoteAuditPacket, build_remote_audit_packet
from router.orchestration.risk_signals import RiskSignalSet, extract_risk_signals
from router.orchestration.state_machine import OrchestrationTrace, build_orchestration_trace


POLICY_PROFILE_BY_ROUTER_POLICY = {
    "aggressive": "adaptive_aggressive",
    "balanced": "adaptive_balanced",
    "conservative": "adaptive_conservative",
}


@dataclass(frozen=True)
class CompetitionDecision:
    action: str
    route: str
    reason: str
    risk_signals: RiskSignalSet
    budget_decision: BudgetDecision
    policy_decision: PolicyDecision
    remote_packet: RemoteAuditPacket
    remote_packet_tokens: int
    final_validation: FinalValidationResult
    final_answer_repaired: bool = False
    dry_run: bool = True
    remote_would_call: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "route": self.route,
            "reason": self.reason,
            "risk_signals": self.risk_signals.to_dict(),
            "budget_decision": self.budget_decision.to_dict(),
            "policy_decision": self.policy_decision.to_dict(),
            "remote_packet": self.remote_packet.to_dict(),
            "remote_packet_tokens": self.remote_packet_tokens,
            "final_validation": self.final_validation.to_dict(),
            "final_answer_repaired": self.final_answer_repaired,
            "dry_run": self.dry_run,
            "remote_would_call": self.remote_would_call,
        }


@dataclass(frozen=True)
class CompetitionTrace:
    task_id: str | None
    decision: CompetitionDecision
    state_trace: OrchestrationTrace
    budget_snapshot: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "decision": self.decision.to_dict(),
            "state_trace": self.state_trace.to_dict(),
            "budget_snapshot": self.budget_snapshot,
        }


class CompetitionRunner:
    """Single competition path that composes the offline orchestration primitives."""

    def __init__(
        self,
        inner: TaskRunner,
        *,
        logger: JsonlRunLogger | None = None,
        budget: TaskBudget | None = None,
        policy: str = "balanced",
        dry_run: bool = True,
    ) -> None:
        self.inner = inner
        self.logger = logger
        self.budget_manager = BudgetManager(budget)
        self.policy = policy
        self.dry_run = dry_run

    def run(self, task: TaskEnvelope) -> AnswerResult:
        guardrail = evaluate_guardrail(task)
        if guardrail is not None:
            candidate = _result_from_guardrail(task, guardrail)
            return self._finish(task, candidate, guardrail_reason=guardrail.reason)

        candidate = self.inner.run(task)
        return self._finish(task, candidate)

    def _finish(
        self,
        task: TaskEnvelope,
        candidate: AnswerResult,
        *,
        guardrail_reason: str = "",
    ) -> AnswerResult:
        signals = extract_risk_signals(
            task,
            candidate_answer=candidate.answer,
            m2a_confidence=str(candidate.metadata.get("m2a_confidence") or ""),
            budget_remaining_ratio=_budget_remaining_ratio(self.budget_manager),
            parse_failure_count=self.budget_manager.parse_failures,
        )
        remote_packet = build_remote_audit_packet(
            task,
            candidate.answer,
            concern=", ".join(signals.reasons) or "risk_within_local_acceptance",
        )
        remote_packet_tokens = remote_packet.approx_tokens()
        preliminary_policy = decide_policy(
            signals,
            thresholds=POLICY_PROFILES[_policy_profile_name(self.policy)],
        )
        estimated_remote_tokens = remote_packet_tokens if preliminary_policy.action == "remote_audit" else 0
        budget_decision = self.budget_manager.allow_remote(
            estimated_remote_tokens=estimated_remote_tokens,
            latency_risk_ms=int(candidate.metadata.get("latency_fireworks_ms") or 0),
        )
        policy_decision = decide_policy(
            signals,
            thresholds=POLICY_PROFILES[_policy_profile_name(self.policy)],
            budget_decision=budget_decision if preliminary_policy.action == "remote_audit" else None,
        )
        route = _competition_route(candidate.route, policy_decision.action)
        answer, validation, repaired = _validated_answer(task, candidate.answer)
        remote_would_call = policy_decision.action == "remote_audit" and budget_decision.allowed
        state_result = AnswerResult(
            id=candidate.id,
            answer=answer,
            route=route,
            remote_tokens=TokenUsage.empty() if self.dry_run else candidate.remote_tokens,
            metadata={**candidate.metadata, "fireworks_parse_failed": False},
        )
        state_trace = build_orchestration_trace(task, state_result, guardrail_reason=guardrail_reason)
        decision = CompetitionDecision(
            action=policy_decision.action,
            route=route,
            reason=policy_decision.reason,
            risk_signals=signals,
            budget_decision=budget_decision,
            policy_decision=policy_decision,
            remote_packet=remote_packet,
            remote_packet_tokens=remote_packet_tokens,
            final_validation=validation,
            final_answer_repaired=repaired,
            dry_run=self.dry_run,
            remote_would_call=remote_would_call,
        )
        competition_trace = CompetitionTrace(
            task_id=task.id,
            decision=decision,
            state_trace=state_trace,
            budget_snapshot=self.budget_manager.snapshot(),
        )
        metadata = _metadata(candidate, validation, repaired, competition_trace, state_trace)
        result = AnswerResult(
            id=candidate.id,
            answer=answer,
            route=route,
            remote_tokens=TokenUsage.empty() if self.dry_run else candidate.remote_tokens,
            metadata=metadata,
        )
        if self.logger:
            self.logger.log_result(
                task,
                result,
                extra={
                    "stage": "competition_mode",
                    "competition_trace": competition_trace.to_dict(),
                },
            )
        return result


def _result_from_guardrail(task: TaskEnvelope, guardrail: GuardrailDecision) -> AnswerResult:
    return AnswerResult(
        id=task.id,
        answer=guardrail.answer,
        route=guardrail.route,
        metadata={
            "runner": "competition_guardrail",
            "reason": guardrail.reason,
        },
    )


def _validated_answer(task: TaskEnvelope, answer: str) -> tuple[str, FinalValidationResult, bool]:
    validation = validate_final_answer(task, answer)
    if not validation.valid and validation.repaired_answer:
        return validation.repaired_answer, validation, True
    return answer, validation, False


def _metadata(
    candidate: AnswerResult,
    validation: FinalValidationResult,
    repaired: bool,
    competition_trace: CompetitionTrace,
    state_trace: OrchestrationTrace,
) -> dict[str, Any]:
    metadata = dict(candidate.metadata)
    metadata.update(
        {
            "runner": "competition",
            "candidate_route": candidate.route,
            "competition_trace": competition_trace.to_dict(),
            "orchestration_trace": state_trace.to_dict(),
            "final_validation": validation.to_dict(),
        }
    )
    if repaired:
        metadata["final_answer_repaired"] = True
    return metadata


def _competition_route(candidate_route: str, action: str) -> str:
    if candidate_route.startswith("guardrail_"):
        return candidate_route
    if action == "approve":
        if candidate_route == "mock_foundation":
            return "m1_approved"
        return candidate_route
    if action == "remote_audit":
        return "m2b_fireworks_approved"
    return "m2b_candidate"


def _budget_remaining_ratio(manager: BudgetManager) -> float:
    snapshot = manager.snapshot()
    max_tokens = snapshot["max_remote_tokens_per_run"]
    if max_tokens <= 0:
        return 0.0
    return snapshot["remote_tokens_remaining"] / max_tokens


def _policy_profile_name(policy: str) -> str:
    normalized = (policy or "balanced").strip().lower()
    if normalized in POLICY_PROFILES:
        return normalized
    return POLICY_PROFILE_BY_ROUTER_POLICY.get(normalized, "adaptive_balanced")
