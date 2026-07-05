from __future__ import annotations

from time import perf_counter

from router.core.auditor import FireworksAuditor
from router.core.contracts import AnswerResult, TaskEnvelope, TokenUsage
from router.core.fireworks import FireworksClient
from router.core.logging import JsonlRunLogger
from router.core.model_client import LocalModelClient, ModelClientError
from router.core.prompts import build_m1_messages
from router.core.repair import LocalRepairGenerator
from router.core.verifier import LocalVerifier


class HybridCascadeRunner:
    """Full local cascade with Fireworks audit only on escalated tasks."""

    def __init__(
        self,
        local_client: LocalModelClient,
        fireworks_client: FireworksClient,
        *,
        logger: JsonlRunLogger | None = None,
        m1_temperature: float = 0.2,
        m1_max_tokens: int = 512,
        m2a_temperature: float = 0.0,
        m2a_max_tokens: int = 256,
        m2b_temperature: float = 0.2,
        m2b_max_tokens: int = 768,
        fireworks_temperature: float = 0.0,
        fireworks_max_tokens: int = 256,
        policy: str = "balanced",
    ) -> None:
        self.local_client = local_client
        self.fireworks_client = fireworks_client
        self.logger = logger
        self.m1_temperature = m1_temperature
        self.m1_max_tokens = m1_max_tokens
        self.verifier = LocalVerifier(
            local_client,
            temperature=m2a_temperature,
            max_tokens=m2a_max_tokens,
            policy=policy,
        )
        self.repair_generator = LocalRepairGenerator(
            local_client,
            temperature=m2b_temperature,
            max_tokens=m2b_max_tokens,
        )
        self.auditor = FireworksAuditor(
            fireworks_client,
            temperature=fireworks_temperature,
            max_tokens=fireworks_max_tokens,
        )

    def run(self, task: TaskEnvelope) -> AnswerResult:
        trace: dict[str, object] = {"stage": "sprint_04"}
        try:
            m1_started_at = perf_counter()
            m1_response = self.local_client.complete(
                build_m1_messages(task),
                temperature=self.m1_temperature,
                max_tokens=self.m1_max_tokens,
            )
            m1_latency_ms = _elapsed_ms(m1_started_at)
        except ModelClientError as exc:
            result = AnswerResult(
                id=task.id,
                answer=f"Local model unavailable: {exc}",
                route="local_error",
                remote_tokens=TokenUsage.empty(),
                metadata={"runner": "hybrid_cascade", "error": str(exc)},
            )
            self._log(task, result, **trace, error=str(exc))
            return result

        m1_candidate = m1_response.text
        trace.update(
            {
                "model_1_candidate_raw": m1_candidate,
                "latency_m1_ms": m1_latency_ms,
                "m1_local_tokens": m1_response.usage.to_dict(),
            }
        )

        verification = self.verifier.verify(task, m1_candidate)
        trace.update(
            {
                "m2a_decision": verification.decision.to_dict(),
                "m2a_raw": verification.raw_text,
                "latency_m2a_ms": verification.latency_ms,
                "m2a_local_tokens": verification.usage.to_dict(),
            }
        )

        if verification.decision.decision == "approve":
            result = AnswerResult(
                id=task.id,
                answer=m1_candidate,
                route="m1_approved",
                remote_tokens=TokenUsage.empty(),
                metadata={
                    "runner": "hybrid_cascade",
                    "local_model": self.local_client.model,
                    "latency_m1_ms": m1_latency_ms,
                    "latency_m2a_ms": verification.latency_ms,
                    "latency_fireworks_ms": 0,
                },
            )
            self._log(task, result, **trace, latency_fireworks_ms=0)
            return result

        try:
            repair = self.repair_generator.generate(task, m1_candidate, verification.decision)
        except ModelClientError as exc:
            result = AnswerResult(
                id=task.id,
                answer=m1_candidate,
                route="m2b_error_return_m1",
                remote_tokens=TokenUsage.empty(),
                metadata={"runner": "hybrid_cascade", "error": str(exc)},
            )
            self._log(task, result, **trace, m2b_error=str(exc), latency_fireworks_ms=0)
            return result

        trace.update(
            {
                "model_2_alternative_raw": repair.answer,
                "latency_m2b_ms": repair.latency_ms,
                "m2b_local_tokens": repair.usage.to_dict(),
            }
        )

        audit = self.auditor.audit(task, m1_candidate, repair.answer, verification.decision)
        trace.update(
            {
                "fireworks_decision": audit.decision.to_dict(),
                "fireworks_raw": audit.raw_text,
                "latency_fireworks_ms": audit.latency_ms,
                "remote_tokens": audit.usage.to_dict(),
            }
        )

        if audit.decision.decision == "approve":
            route = "m2b_fireworks_approved" if audit.raw_text else "m2b_fireworks_error_approved"
            answer = repair.answer
        else:
            route = "fireworks_replaced"
            answer = audit.decision.answer

        result = AnswerResult(
            id=task.id,
            answer=answer,
            route=route,
            remote_tokens=audit.usage,
            metadata={
                "runner": "hybrid_cascade",
                "local_model": self.local_client.model,
                "fireworks_model": self.fireworks_client.model,
                "latency_m1_ms": m1_latency_ms,
                "latency_m2a_ms": verification.latency_ms,
                "latency_m2b_ms": repair.latency_ms,
                "latency_fireworks_ms": audit.latency_ms,
                "fireworks_parse_failed": audit.decision.parse_failed,
            },
        )
        self._log(task, result, **trace)
        return result

    def _log(self, task: TaskEnvelope, result: AnswerResult, **extra: object) -> None:
        if self.logger:
            self.logger.log_result(task, result, extra=extra)


def _elapsed_ms(started_at: float) -> int:
    return round((perf_counter() - started_at) * 1000)
