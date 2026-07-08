from __future__ import annotations

from time import perf_counter

from router.core.contracts import AnswerResult, TaskEnvelope, TokenUsage
from router.core.fireworks import FireworksClient
from router.core.logging import JsonlRunLogger
from router.core.model_client import ModelClientError, ModelResponse
from router.core.prompts import build_m1_messages
from router.orchestration.fireworks_model_router import select_fireworks_model, select_reasoning_effort
from router.orchestration.solvers import solve_deterministic


class FireworksDirectRunner:
    """Official fallback runner: deterministic solvers first, Fireworks direct otherwise."""

    def __init__(
        self,
        client: FireworksClient,
        *,
        logger: JsonlRunLogger | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
        allowed_models: list[str] | None = None,
        service_tier: str | None = None,
    ) -> None:
        self.client = client
        self.logger = logger
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.allowed_models = allowed_models or []
        self.service_tier = service_tier

    def run(self, task: TaskEnvelope) -> AnswerResult:
        solver = solve_deterministic(task)
        if solver is not None:
            result = AnswerResult(
                id=task.id,
                answer=solver.answer,
                route=solver.route,
                remote_tokens=TokenUsage.empty(),
                metadata={
                    "runner": "fireworks_direct",
                    "solver": solver.to_dict(),
                    "reason": solver.reason,
                },
            )
            self._log(task, result, stage="deterministic_solver", solver=solver.to_dict())
            return result

        started_at = perf_counter()
        selection = select_fireworks_model(task, self.allowed_models, default_model=self.client.model)
        request_options = _request_options_for_selection(selection.model, selection.tier, service_tier=self.service_tier)
        request_options_fallback: str | None = None
        original_model = self.client.model
        self.client.model = selection.model
        try:
            response = _complete_with_optional_request_options(
                self.client,
                build_m1_messages(task),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                request_options=request_options,
            )
        except _RequestOptionsFallback as fallback:
            response = fallback.response
            request_options_fallback = fallback.reason
        except ModelClientError as exc:
            latency_ms = _elapsed_ms(started_at)
            result = AnswerResult(
                id=task.id,
                answer="Unable to complete the task.",
                route="fireworks_error",
                remote_tokens=TokenUsage.empty(),
                metadata={
                    "runner": "fireworks_direct",
                    "fireworks_model": selection.model,
                    "fireworks_model_selection": selection.to_dict(),
                    "fireworks_request_options": request_options,
                    "latency_fireworks_ms": latency_ms,
                    "error": str(exc),
                },
            )
            self._log(
                task,
                result,
                stage="fireworks_direct_error",
                error=str(exc),
                latency_fireworks_ms=latency_ms,
                fireworks_request_options=request_options,
            )
            return result
        finally:
            self.client.model = original_model

        latency_ms = _elapsed_ms(started_at)
        result = AnswerResult(
            id=task.id,
            answer=response.text,
            route="fireworks_direct",
            remote_tokens=response.usage,
            metadata={
                "runner": "fireworks_direct",
                "fireworks_model": selection.model,
                "fireworks_model_selection": selection.to_dict(),
                "fireworks_request_options": request_options,
                "fireworks_request_options_fallback": request_options_fallback,
                "latency_fireworks_ms": latency_ms,
            },
        )
        self._log(
            task,
            result,
            stage="fireworks_direct",
            latency_fireworks_ms=latency_ms,
            fireworks_tokens=response.usage.to_dict(),
            fireworks_request_options=request_options,
            fireworks_request_options_fallback=request_options_fallback,
        )
        return result

    def _log(self, task: TaskEnvelope, result: AnswerResult, **extra: object) -> None:
        if self.logger:
            self.logger.log_result(task, result, extra=extra)


def _elapsed_ms(started_at: float) -> int:
    return round((perf_counter() - started_at) * 1000)


def _request_options_for_selection(model: str, tier: str, *, service_tier: str | None = None) -> dict[str, object]:
    options: dict[str, object] = {"user": "track1-token-router-v1"}
    if service_tier:
        options["service_tier"] = service_tier
    reasoning_effort = select_reasoning_effort(model, tier)
    if reasoning_effort:
        options["reasoning_effort"] = reasoning_effort
    return options


def _complete_with_optional_request_options(
    client: FireworksClient,
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
    request_options: dict[str, object],
) -> ModelResponse:
    try:
        return client.complete(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=request_options or None,
        )
    except ModelClientError as exc:
        if request_options and _is_request_option_error(str(exc)):
            response = client.complete(messages, temperature=temperature, max_tokens=max_tokens)
            raise _RequestOptionsFallback(response, str(exc)) from exc
        raise


def _is_request_option_error(message: str) -> bool:
    lowered = message.lower()
    return "reasoning_effort" in lowered or "service_tier" in lowered or "extra inputs are not permitted" in lowered


class _RequestOptionsFallback(Exception):
    def __init__(self, response: ModelResponse, reason: str) -> None:
        super().__init__(reason)
        self.response = response
        self.reason = reason
