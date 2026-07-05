from __future__ import annotations

from time import perf_counter

from router.core.contracts import AnswerResult, TaskEnvelope, TokenUsage
from router.core.logging import JsonlRunLogger
from router.core.model_client import LocalModelClient, ModelClientError
from router.core.prompts import build_m1_messages


class LocalM1Runner:
    """Sprint 02 runner: calls the local model once and returns its free-form answer."""

    def __init__(
        self,
        client: LocalModelClient,
        *,
        logger: JsonlRunLogger | None = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> None:
        self.client = client
        self.logger = logger
        self.temperature = temperature
        self.max_tokens = max_tokens

    def run(self, task: TaskEnvelope) -> AnswerResult:
        started_at = perf_counter()
        try:
            response = self.client.complete(
                build_m1_messages(task),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except ModelClientError as exc:
            latency_ms = _elapsed_ms(started_at)
            result = AnswerResult(
                id=task.id,
                answer=f"Local model unavailable: {exc}",
                route="local_error",
                remote_tokens=TokenUsage.empty(),
                metadata={
                    "runner": "local_m1",
                    "local_model": self.client.model,
                    "latency_m1_ms": latency_ms,
                    "error": str(exc),
                },
            )
            self._log(task, result, latency_ms=latency_ms, error=str(exc))
            return result

        latency_ms = _elapsed_ms(started_at)
        candidate = response.text
        result = AnswerResult(
            id=task.id,
            answer=candidate,
            route="m1_local",
            remote_tokens=TokenUsage.empty(),
            metadata={
                "runner": "local_m1",
                "local_model": self.client.model,
                "latency_m1_ms": latency_ms,
                "model_1_candidate_chars": len(candidate),
                "local_tokens": response.usage.to_dict(),
            },
        )
        self._log(
            task,
            result,
            latency_ms=latency_ms,
            model_1_candidate_raw=candidate,
            local_tokens=response.usage.to_dict(),
        )
        return result

    def _log(self, task: TaskEnvelope, result: AnswerResult, **extra: object) -> None:
        if self.logger:
            self.logger.log_result(
                task,
                result,
                extra={
                    "stage": "sprint_02",
                    **extra,
                },
            )


def _elapsed_ms(started_at: float) -> int:
    return round((perf_counter() - started_at) * 1000)

