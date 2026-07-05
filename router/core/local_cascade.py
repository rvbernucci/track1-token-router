from __future__ import annotations

from time import perf_counter

from router.core.contracts import AnswerResult, TaskEnvelope, TokenUsage
from router.core.logging import JsonlRunLogger
from router.core.model_client import LocalModelClient, ModelClientError
from router.core.prompts import build_m1_messages
from router.core.repair import LocalRepairGenerator
from router.core.verifier import LocalVerifier, VerificationResult


class LocalCascadeRunner:
    """Local-only cascade: M1 candidate, M2A verifier, optional M2B repair."""

    def __init__(
        self,
        client: LocalModelClient,
        *,
        logger: JsonlRunLogger | None = None,
        m1_temperature: float = 0.2,
        m1_max_tokens: int = 512,
        m2a_temperature: float = 0.0,
        m2a_max_tokens: int = 256,
        m2b_temperature: float = 0.2,
        m2b_max_tokens: int = 768,
    ) -> None:
        self.client = client
        self.logger = logger
        self.m1_temperature = m1_temperature
        self.m1_max_tokens = m1_max_tokens
        self.verifier = LocalVerifier(
            client,
            temperature=m2a_temperature,
            max_tokens=m2a_max_tokens,
        )
        self.repair_generator = LocalRepairGenerator(
            client,
            temperature=m2b_temperature,
            max_tokens=m2b_max_tokens,
        )

    def run(self, task: TaskEnvelope) -> AnswerResult:
        trace: dict[str, object] = {"stage": "sprint_03"}
        try:
            m1_started_at = perf_counter()
            m1_response = self.client.complete(
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
                metadata={"runner": "local_cascade", "error": str(exc)},
            )
            self._log(task, result, **trace, error=str(exc))
            return result

        candidate = m1_response.text
        trace.update(
            {
                "model_1_candidate_raw": candidate,
                "latency_m1_ms": m1_latency_ms,
                "m1_local_tokens": m1_response.usage.to_dict(),
            }
        )

        verification = self.verifier.verify(task, candidate)
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
                answer=candidate,
                route="m1_approved",
                remote_tokens=TokenUsage.empty(),
                metadata={
                    "runner": "local_cascade",
                    "local_model": self.client.model,
                    "latency_m1_ms": m1_latency_ms,
                    "latency_m2a_ms": verification.latency_ms,
                    "m2a_confidence": verification.decision.confidence,
                },
            )
            self._log(task, result, **trace)
            return result

        try:
            repair = self.repair_generator.generate(task, candidate, verification.decision)
        except ModelClientError as exc:
            trace["m2b_error"] = str(exc)
            result = AnswerResult(
                id=task.id,
                answer=candidate,
                route="m2b_error_return_m1",
                remote_tokens=TokenUsage.empty(),
                metadata={
                    "runner": "local_cascade",
                    "local_model": self.client.model,
                    "error": str(exc),
                },
            )
            self._log(task, result, **trace)
            return result

        trace.update(
            {
                "model_2_alternative_raw": repair.answer,
                "latency_m2b_ms": repair.latency_ms,
                "m2b_local_tokens": repair.usage.to_dict(),
            }
        )
        result = AnswerResult(
            id=task.id,
            answer=repair.answer,
            route="m2b_candidate",
            remote_tokens=TokenUsage.empty(),
            metadata={
                "runner": "local_cascade",
                "local_model": self.client.model,
                "latency_m1_ms": m1_latency_ms,
                "latency_m2a_ms": verification.latency_ms,
                "latency_m2b_ms": repair.latency_ms,
                "m2a_confidence": verification.decision.confidence,
            },
        )
        self._log(task, result, **trace)
        return result

    def _log(self, task: TaskEnvelope, result: AnswerResult, **extra: object) -> None:
        if self.logger:
            self.logger.log_result(task, result, extra=extra)


def _elapsed_ms(started_at: float) -> int:
    return round((perf_counter() - started_at) * 1000)

