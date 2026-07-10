from __future__ import annotations

from time import perf_counter

from router.core.contracts import AnswerResult, TaskEnvelope, TokenUsage
from router.core.model_client import LocalModelClient, ModelClientError


class GemmaE2BRunner:
    def __init__(
        self,
        client: LocalModelClient,
        *,
        max_tokens: int = 96,
        temperature: float = 0.0,
    ) -> None:
        if max_tokens < 1:
            raise ValueError("E2B max_tokens must be positive.")
        self.client = client
        self.max_tokens = max_tokens
        self.temperature = temperature

    def run(self, task: TaskEnvelope) -> AnswerResult:
        started = perf_counter()
        try:
            response = self.client.complete(
                [{"role": "user", "content": task.input_text}],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                extra_body={"max_completion_tokens": self.max_tokens},
            )
        except ModelClientError as exc:
            return AnswerResult(
                id=task.id,
                answer="",
                route="e2b_error",
                remote_tokens=TokenUsage.empty(),
                metadata={
                    "runner": "gemma_e2b",
                    "model": self.client.model,
                    "generation_limit_tokens": self.max_tokens,
                    "latency_e2b_ms": _elapsed_ms(started),
                    "error": str(exc),
                },
            )
        return AnswerResult(
            id=task.id,
            answer=response.text.strip(),
            route="e2b_local",
            remote_tokens=TokenUsage.empty(),
            metadata={
                "runner": "gemma_e2b",
                "model": self.client.model,
                "generation_limit_tokens": self.max_tokens,
                "latency_e2b_ms": _elapsed_ms(started),
                "local_tokens": response.usage.to_dict(),
            },
        )


def _elapsed_ms(started: float) -> int:
    return round((perf_counter() - started) * 1000)
