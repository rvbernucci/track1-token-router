from __future__ import annotations

from time import perf_counter

from router.core.contracts import AnswerResult, TaskEnvelope, TokenUsage
from router.core.model_client import LocalModelClient, ModelClientError
E2B_PROMPT_VERSION = "generic-answer-contract-v2-english"
E2B_SYSTEM_PROMPT = (
    "Answer the user's task directly and correctly. Follow every explicit output-format "
    "constraint exactly. Return only the requested answer; do not add a preamble, explanation, "
    "or markdown unless the user explicitly requests it. Use English for all natural-language "
    "text. Preserve required code, JSON keys, labels, names, and quoted source spans exactly."
)


def build_e2b_messages(input_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": E2B_SYSTEM_PROMPT},
        {"role": "user", "content": input_text},
    ]


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
        return self._run_with_limit(task, max_tokens=self.max_tokens, route="e2b_local", retry=False)

    def retry(self, task: TaskEnvelope) -> AnswerResult:
        return self._run_with_limit(task, max_tokens=self.max_tokens * 2, route="e2b_local_retry", retry=True)

    def _run_with_limit(
        self,
        task: TaskEnvelope,
        *,
        max_tokens: int,
        route: str,
        retry: bool,
    ) -> AnswerResult:
        started = perf_counter()
        try:
            response = self.client.complete(
                build_e2b_messages(task.input_text),
                temperature=self.temperature,
                max_tokens=max_tokens,
                extra_body={"max_completion_tokens": max_tokens},
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
                    "prompt_version": E2B_PROMPT_VERSION,
                    "generation_limit_tokens": max_tokens,
                    "contract_retry": retry,
                    "latency_e2b_ms": _elapsed_ms(started),
                    "error": str(exc),
                },
            )
        return AnswerResult(
            id=task.id,
            answer=response.text.strip(),
            route=route,
            remote_tokens=TokenUsage.empty(),
            metadata={
                "runner": "gemma_e2b",
                "model": self.client.model,
                "prompt_version": E2B_PROMPT_VERSION,
                "generation_limit_tokens": max_tokens,
                "contract_retry": retry,
                "latency_e2b_ms": _elapsed_ms(started),
                "local_tokens": response.usage.to_dict(),
            },
        )


def _elapsed_ms(started: float) -> int:
    return round((perf_counter() - started) * 1000)
