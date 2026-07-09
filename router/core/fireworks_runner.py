from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

from router.core.contracts import AnswerResult, TaskEnvelope, TokenUsage
from router.core.fireworks import FireworksClient
from router.core.logging import JsonlRunLogger
from router.core.model_client import ModelClientError, ModelResponse
from router.core.prompts import build_m1_messages
from router.orchestration.fireworks_model_router import select_fireworks_model, select_reasoning_effort
from router.orchestration.final_validator import validate_final_answer
from router.orchestration.matrix_regression_selector import (
    MatrixRegressionWeights,
    load_weights,
    select_model_by_matrix_regression,
)
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
        matrix_weights_path: Path | None = None,
    ) -> None:
        self.client = client
        self.logger = logger
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.allowed_models = allowed_models or []
        self.service_tier = service_tier
        self.matrix_weights_path = matrix_weights_path
        self._matrix_weights: MatrixRegressionWeights | None = None
        self._matrix_error: str | None = None
        self._unavailable_models: set[str] = set()

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
        matrix_selection = self._matrix_selection(task)
        selected_model = str(matrix_selection.get("model") or selection.model) if matrix_selection else selection.model
        request_options = _request_options_for_selection(selected_model, selection.tier, service_tier=self.service_tier)
        request_options_fallback: str | None = None
        original_model = self.client.model
        attempt_errors: list[dict[str, str]] = []
        response: ModelResponse | None = None
        try:
            for attempt_model in _models_to_try(
                selection,
                matrix_selection=matrix_selection,
                first_model=selected_model,
                unavailable_models=self._unavailable_models,
            ):
                selected_model = attempt_model
                request_options = _request_options_for_selection(
                    selected_model,
                    selection.tier,
                    service_tier=self.service_tier,
                )
                self.client.model = selected_model
                try:
                    response = _complete_with_optional_request_options(
                        self.client,
                        build_m1_messages(task),
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        request_options=request_options,
                    )
                    break
                except _RequestOptionsFallback as fallback:
                    response = fallback.response
                    request_options_fallback = fallback.reason
                    break
                except ModelClientError as exc:
                    error = str(exc)
                    attempt_errors.append({"model": selected_model, "error": error})
                    if _is_timeout_error(error):
                        break
                    if _is_unavailable_model_error(error):
                        self._unavailable_models.add(selected_model)
                    continue
        finally:
            self.client.model = original_model

        if response is None:
            latency_ms = _elapsed_ms(started_at)
            result = AnswerResult(
                id=task.id,
                answer="Unable to complete the task.",
                route="fireworks_error",
                remote_tokens=TokenUsage.empty(),
                metadata={
                    "runner": "fireworks_direct",
                    "fireworks_model": selected_model,
                    "fireworks_model_selection": selection.to_dict(),
                    "fireworks_matrix_selection": matrix_selection,
                    "fireworks_request_options": request_options,
                    "fireworks_attempt_errors": attempt_errors,
                    "fireworks_unavailable_models": sorted(self._unavailable_models),
                    "latency_fireworks_ms": latency_ms,
                    "error": attempt_errors[-1]["error"] if attempt_errors else "no_model_attempted",
                },
            )
            self._log(
                task,
                result,
                stage="fireworks_direct_error",
                error=result.metadata["error"],
                latency_fireworks_ms=latency_ms,
                fireworks_request_options=request_options,
                fireworks_attempt_errors=attempt_errors,
                fireworks_matrix_selection=matrix_selection,
                fireworks_unavailable_models=sorted(self._unavailable_models),
            )
            return result

        latency_ms = _elapsed_ms(started_at)
        final_validation = validate_final_answer(task, response.text)
        final_answer = final_validation.repaired_answer if not final_validation.valid and final_validation.repaired_answer else response.text
        result = AnswerResult(
            id=task.id,
            answer=final_answer,
            route="fireworks_direct",
            remote_tokens=response.usage,
            metadata={
                "runner": "fireworks_direct",
                "fireworks_model": selected_model,
                "fireworks_model_selection": selection.to_dict(),
                "fireworks_matrix_selection": matrix_selection,
                "fireworks_request_options": request_options,
                "fireworks_request_options_fallback": request_options_fallback,
                "fireworks_attempt_errors": attempt_errors,
                "fireworks_unavailable_models": sorted(self._unavailable_models),
                "latency_fireworks_ms": latency_ms,
                "final_validation": final_validation.to_dict(),
                "final_answer_repaired": final_answer != response.text,
            },
        )
        self._log(
            task,
            result,
            stage="fireworks_direct",
            latency_fireworks_ms=latency_ms,
            fireworks_tokens=response.usage.to_dict(),
            fireworks_model=selected_model,
            fireworks_request_options=request_options,
            fireworks_request_options_fallback=request_options_fallback,
            fireworks_attempt_errors=attempt_errors,
            fireworks_matrix_selection=matrix_selection,
            fireworks_unavailable_models=sorted(self._unavailable_models),
        )
        return result

    def _log(self, task: TaskEnvelope, result: AnswerResult, **extra: object) -> None:
        if self.logger:
            self.logger.log_result(task, result, extra=extra)

    def _matrix_selection(self, task: TaskEnvelope) -> dict[str, Any] | None:
        if self.matrix_weights_path is None:
            return None
        if self._matrix_error:
            return {"error": self._matrix_error}
        try:
            if self._matrix_weights is None:
                self._matrix_weights = load_weights(self.matrix_weights_path)
            models = self.allowed_models or [self.client.model]
            return select_model_by_matrix_regression(task, models, self._matrix_weights)
        except Exception as exc:
            self._matrix_error = str(exc)
            return {"error": self._matrix_error}


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


def _models_to_try(
    selection: object,
    *,
    matrix_selection: dict[str, Any] | None = None,
    first_model: str | None = None,
    unavailable_models: set[str] | None = None,
) -> list[str]:
    models: list[str] = []
    unavailable = unavailable_models or set()

    def add(model: object) -> None:
        if isinstance(model, str) and model and model not in unavailable and model not in models:
            models.append(model)

    add(first_model)
    if matrix_selection:
        ranked = matrix_selection.get("ranked_candidates")
        if isinstance(ranked, list):
            for candidate in ranked:
                if isinstance(candidate, dict):
                    add(candidate.get("model"))
    add(getattr(selection, "model", ""))
    candidates = getattr(selection, "candidates", [])
    if isinstance(candidates, list):
        sorted_candidates = sorted(
            [candidate for candidate in candidates if isinstance(candidate, dict) and candidate.get("supports_chat")],
            key=lambda candidate: (
                float(candidate.get("nash_product") or 0.0),
                float(candidate.get("prisoner_payoff") or 0.0),
                -float(candidate.get("estimated_cost_usd") or 0.0),
            ),
            reverse=True,
        )
        for candidate in sorted_candidates:
            add(candidate.get("model"))
    ranked_models = getattr(selection, "ranked_models", [])
    if isinstance(ranked_models, list):
        for model in ranked_models:
            add(model)
    return models


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


def _is_unavailable_model_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "http 404" in lowered
        or "model not found" in lowered
        or "inaccessible" in lowered
        or "not deployed" in lowered
    )


def _is_timeout_error(message: str) -> bool:
    lowered = message.lower()
    return "timed out" in lowered or "timeout" in lowered


class _RequestOptionsFallback(Exception):
    def __init__(self, response: ModelResponse, reason: str) -> None:
        super().__init__(reason)
        self.response = response
        self.reason = reason
