from __future__ import annotations

from router.core.contracts import AnswerResult, EngineDecision, RoutingTrace, TaskEnvelope
from router.core.logging import JsonlRunLogger
from router.core.runner import TaskRunner


class AssessmentSafeModeRunner:
    """Keeps the new runtime fail-closed until assessment and regressions are promoted."""

    def __init__(
        self,
        fallback: TaskRunner,
        *,
        logger: JsonlRunLogger | None = None,
        reason: str = "assessment_or_decision_artifact_unavailable",
    ) -> None:
        self.fallback = fallback
        self.logger = logger
        self.reason = reason

    def run(self, task: TaskEnvelope) -> AnswerResult:
        decision = EngineDecision.fireworks_safe_fallback(self.reason)
        candidate = self.fallback.run(task)
        trace = RoutingTrace(
            task_id=task.id,
            assessment=None,
            features=None,
            predictions=(),
            decision=decision,
            fallback=self.reason,
        )
        metadata = dict(candidate.metadata)
        metadata.update(
            {
                "routing_trace": trace.to_dict(),
                "assessment_status": "safe_fallback",
                "assessment_fallback_reason": self.reason,
            }
        )
        result = AnswerResult(
            id=candidate.id,
            answer=candidate.answer,
            route=candidate.route,
            remote_tokens=candidate.remote_tokens,
            metadata=metadata,
        )
        if self.logger:
            self.logger.log_result(
                task,
                result,
                extra={"stage": "assessment_safe_mode", "routing_trace": trace.to_dict()},
            )
        return result
