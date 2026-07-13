from __future__ import annotations

import json
import math
import re
from pathlib import Path
from time import perf_counter
from typing import Any

from router.core.contracts import AnswerResult, TaskEnvelope, TokenUsage
from router.core.fireworks import FireworksClient
from router.core.logging import JsonlRunLogger
from router.core.model_client import ModelClientError, ModelResponse
from router.core.prompts import FIREWORKS_ANSWER_PROMPT_VERSION, build_fireworks_answer_messages
from router.orchestration.fireworks_model_router import (
    normalize_fireworks_model_id,
    select_fireworks_model,
    select_reasoning_effort,
)
from router.orchestration.fireworks_intent_policy import FireworksIntentPolicy
from router.orchestration.final_validator import (
    AnswerContractKind,
    infer_answer_contract,
    validate_final_answer,
    validate_or_safely_repair_final_answer,
)
from router.orchestration.matrix_regression_selector import (
    MatrixRegressionWeights,
    load_weights,
    select_model_by_matrix_regression,
)
from router.orchestration.prompt_packet import extract_literal_echo
from router.orchestration.solvers import solve_deterministic


FIREWORKS_COMPLETION_POLICY_VERSION = "accuracy-first-contract-v5"


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
        champion_model: str | None = None,
        matrix_weights_path: Path | None = None,
        intent_policy_path: Path | None = None,
        intent_policy_sha256: str | None = None,
        enable_deterministic_solvers: bool = True,
    ) -> None:
        self.client = client
        self.logger = logger
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.allowed_models = [normalize_fireworks_model_id(model) for model in (allowed_models or [])]
        self.service_tier = service_tier
        self.champion_model = normalize_fireworks_model_id(champion_model) or None
        self.matrix_weights_path = matrix_weights_path
        self.intent_policy_path = intent_policy_path
        self.intent_policy_sha256 = intent_policy_sha256
        self.enable_deterministic_solvers = enable_deterministic_solvers
        self._matrix_weights: MatrixRegressionWeights | None = None
        self._matrix_error: str | None = None
        self._intent_policy: FireworksIntentPolicy | None = None
        self._intent_policy_error: str | None = None
        self._unavailable_models: set[str] = set()

    def run(self, task: TaskEnvelope) -> AnswerResult:
        solver = solve_deterministic(task) if self.enable_deterministic_solvers else None
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
        selection, matrix_selection, intent_policy_selection, champion_selection, selected_model = self._selection_plan(task)
        request_options = _request_options_for_selection(selected_model, selection.tier, service_tier=self.service_tier)
        request_options_fallback: str | None = None
        original_model = self.client.model
        attempt_errors: list[dict[str, str]] = []
        invalid_attempts: list[dict[str, object]] = []
        response: ModelResponse | None = None
        final_validation = None
        safe_validation = None
        last_invalid_response: ModelResponse | None = None
        last_invalid_validation = None
        last_invalid_safe_validation = None
        total_usage = TokenUsage.empty()
        token_policy = _completion_token_policy(
            task,
            tier=selection.tier,
            domain=selection.domain,
            configured_max_tokens=self.max_tokens,
        )
        request_max_tokens = int(token_policy["max_tokens"])
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
                        build_fireworks_answer_messages(task, domain=selection.domain),
                        temperature=self.temperature,
                        max_tokens=request_max_tokens,
                        request_options=request_options,
                    )
                    total_usage = _add_usage(total_usage, response.usage)
                    response, retry_usage, retry_metadata = _retry_truncated_response(
                        self.client,
                        task,
                        response,
                        domain=selection.domain,
                        temperature=self.temperature,
                        initial_max_tokens=request_max_tokens,
                        configured_max_tokens=self.max_tokens,
                        request_options=request_options,
                    )
                    total_usage = _add_usage(total_usage, retry_usage)
                    if retry_metadata:
                        token_policy["truncation_retry"] = retry_metadata
                    final_validation = validate_final_answer(task, response.text)
                    safe_validation = validate_or_safely_repair_final_answer(task, response.text)
                    if (
                        not safe_validation.valid
                        and _should_retry_invalid_final_answer(safe_validation.reason)
                    ):
                        invalid_attempts.append(
                            {
                                "model": selected_model,
                                "reason": final_validation.reason,
                                "expected_format": final_validation.expected_format,
                                "max_tokens": request_max_tokens,
                                "usage": response.usage.to_dict(),
                            }
                        )
                        last_invalid_response = response
                        last_invalid_validation = final_validation
                        last_invalid_safe_validation = safe_validation
                        response = None
                        continue
                    break
                except _RequestOptionsFallback as fallback:
                    response = fallback.response
                    total_usage = _add_usage(total_usage, response.usage)
                    response, retry_usage, retry_metadata = _retry_truncated_response(
                        self.client,
                        task,
                        response,
                        domain=selection.domain,
                        temperature=self.temperature,
                        initial_max_tokens=request_max_tokens,
                        configured_max_tokens=self.max_tokens,
                        request_options={},
                    )
                    total_usage = _add_usage(total_usage, retry_usage)
                    if retry_metadata:
                        token_policy["truncation_retry"] = retry_metadata
                    final_validation = validate_final_answer(task, response.text)
                    safe_validation = validate_or_safely_repair_final_answer(task, response.text)
                    request_options_fallback = fallback.reason
                    if (
                        not safe_validation.valid
                        and _should_retry_invalid_final_answer(safe_validation.reason)
                    ):
                        invalid_attempts.append(
                            {
                                "model": selected_model,
                                "reason": final_validation.reason,
                                "expected_format": final_validation.expected_format,
                                "max_tokens": request_max_tokens,
                                "usage": response.usage.to_dict(),
                            }
                        )
                        last_invalid_response = response
                        last_invalid_validation = final_validation
                        last_invalid_safe_validation = safe_validation
                        response = None
                        continue
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

        if response is None and last_invalid_response is not None:
            response = last_invalid_response
            final_validation = last_invalid_validation
            safe_validation = last_invalid_safe_validation

        if response is None:
            latency_ms = _elapsed_ms(started_at)
            result = AnswerResult(
                id=task.id,
                answer="Unable to complete the task.",
                route="fireworks_error",
                remote_tokens=TokenUsage.empty(),
                metadata={
                    "runner": "fireworks_direct",
                    "answer_prompt_version": FIREWORKS_ANSWER_PROMPT_VERSION,
                    "fireworks_model": selected_model,
                    "fireworks_model_selection": selection.to_dict(),
                    "fireworks_matrix_selection": matrix_selection,
                    "fireworks_intent_policy_selection": intent_policy_selection,
                    "fireworks_champion_selection": champion_selection,
                    "fireworks_request_options": request_options,
                    "fireworks_completion_token_policy": token_policy,
                    "fireworks_attempt_errors": attempt_errors,
                    "fireworks_invalid_attempts": invalid_attempts,
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
                fireworks_completion_token_policy=token_policy,
                fireworks_attempt_errors=attempt_errors,
                fireworks_invalid_attempts=invalid_attempts,
                fireworks_matrix_selection=matrix_selection,
                fireworks_intent_policy_selection=intent_policy_selection,
                fireworks_champion_selection=champion_selection,
                fireworks_unavailable_models=sorted(self._unavailable_models),
            )
            return result

        latency_ms = _elapsed_ms(started_at)
        if final_validation is None:
            final_validation = validate_final_answer(task, response.text)
        if safe_validation is None:
            safe_validation = validate_or_safely_repair_final_answer(task, response.text)
        final_answer = safe_validation.repaired_answer if safe_validation.valid and safe_validation.repaired_answer else response.text
        result = AnswerResult(
            id=task.id,
            answer=final_answer,
            route="fireworks_direct",
            remote_tokens=total_usage,
            metadata={
                "runner": "fireworks_direct",
                "answer_prompt_version": FIREWORKS_ANSWER_PROMPT_VERSION,
                "fireworks_model": selected_model,
                "fireworks_model_selection": selection.to_dict(),
                "fireworks_matrix_selection": matrix_selection,
                "fireworks_intent_policy_selection": intent_policy_selection,
                "fireworks_champion_selection": champion_selection,
                "fireworks_request_options": request_options,
                "fireworks_request_options_fallback": request_options_fallback,
                "fireworks_completion_token_policy": token_policy,
                "fireworks_attempt_errors": attempt_errors,
                "fireworks_invalid_attempts": invalid_attempts,
                "fireworks_unavailable_models": sorted(self._unavailable_models),
                "latency_fireworks_ms": latency_ms,
                "final_validation": final_validation.to_dict(),
                "safe_final_validation": safe_validation.to_dict(),
                "final_answer_repaired": final_answer != response.text,
            },
        )
        self._log(
            task,
            result,
            stage="fireworks_direct",
            latency_fireworks_ms=latency_ms,
            fireworks_tokens=total_usage.to_dict(),
            fireworks_model=selected_model,
            fireworks_request_options=request_options,
            fireworks_request_options_fallback=request_options_fallback,
            fireworks_completion_token_policy=token_policy,
            fireworks_attempt_errors=attempt_errors,
            fireworks_invalid_attempts=invalid_attempts,
            fireworks_matrix_selection=matrix_selection,
            fireworks_intent_policy_selection=intent_policy_selection,
            fireworks_champion_selection=champion_selection,
            fireworks_unavailable_models=sorted(self._unavailable_models),
        )
        return result

    def planned_model(self, task: TaskEnvelope) -> str:
        return self._selection_plan(task)[4]

    def _selection_plan(self, task: TaskEnvelope):
        selection = select_fireworks_model(task, self.allowed_models, default_model=self.client.model)
        matrix_selection = self._matrix_selection(task)
        intent_policy_selection = self._intent_policy_selection(selection.domain)
        champion_selection = self._champion_selection(selection.domain)
        if champion_selection and champion_selection.get("model"):
            selected_model = str(champion_selection["model"])
        elif intent_policy_selection and intent_policy_selection.get("model"):
            selected_model = str(intent_policy_selection["model"])
        elif matrix_selection:
            selected_model = str(matrix_selection.get("model") or selection.model)
        else:
            selected_model = selection.model
        return selection, matrix_selection, intent_policy_selection, champion_selection, selected_model

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

    def _intent_policy_selection(self, domain: str) -> dict[str, Any] | None:
        if self.intent_policy_path is None:
            return None
        if self._intent_policy_error:
            return {"error": self._intent_policy_error}
        try:
            if self._intent_policy is None:
                self._intent_policy = FireworksIntentPolicy.load(
                    self.intent_policy_path,
                    expected_sha256=self.intent_policy_sha256,
                )
            models = self.allowed_models or [self.client.model]
            return self._intent_policy.select(domain=domain, runtime_allowed_models=models)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._intent_policy_error = str(exc)
            return {"error": self._intent_policy_error}

    def _champion_selection(self, domain: str) -> dict[str, Any] | None:
        if not self.champion_model:
            return None
        runtime_allowed = set(self.allowed_models or [self.client.model])
        if self.champion_model not in runtime_allowed:
            return {
                "domain": domain,
                "preferred_model": self.champion_model,
                "reason": "champion_not_runtime_allowed",
                "selection_rule": "validation_selected_global_champion",
            }
        return {
            "domain": domain,
            "model": self.champion_model,
            "reason": "champion_is_runtime_allowed",
            "selection_rule": "validation_selected_global_champion",
        }


def _elapsed_ms(started_at: float) -> int:
    return round((perf_counter() - started_at) * 1000)


def _add_usage(left: TokenUsage, right: TokenUsage) -> TokenUsage:
    return TokenUsage(
        prompt=left.prompt + right.prompt,
        completion=left.completion + right.completion,
        total=left.total + right.total,
    )


def _should_retry_invalid_final_answer(reason: str) -> bool:
    return reason in {
        "empty_answer",
        "invalid_json",
        "not_number_only",
        "not_yes_no",
        "invalid_python_code",
        "code_with_extra_text",
    }


def _request_options_for_selection(model: str, tier: str, *, service_tier: str | None = None) -> dict[str, object]:
    options: dict[str, object] = {"user": "track1-token-router-v1"}
    if service_tier:
        options["service_tier"] = service_tier
    reasoning_effort = select_reasoning_effort(model, tier)
    if reasoning_effort:
        options["reasoning_effort"] = reasoning_effort
    return options


def _completion_token_policy(
    task: TaskEnvelope,
    *,
    tier: str,
    domain: str,
    configured_max_tokens: int,
) -> dict[str, object]:
    contract = infer_answer_contract(task)
    expected_format = contract.kind.value
    policy_cap = _completion_token_cap(task, expected_format=expected_format, tier=tier, domain=domain)
    configured_cap = max(1, configured_max_tokens)
    max_tokens = min(configured_cap, policy_cap)
    return {
        "policy_version": FIREWORKS_COMPLETION_POLICY_VERSION,
        "max_tokens": max_tokens,
        "configured_max_tokens": configured_cap,
        "policy_cap": policy_cap,
        "expected_format": expected_format,
        "tier": tier,
        "domain": domain,
    }


def _retry_truncated_response(
    client: FireworksClient,
    task: TaskEnvelope,
    response: ModelResponse,
    *,
    domain: str,
    temperature: float,
    initial_max_tokens: int,
    configured_max_tokens: int,
    request_options: dict[str, Any],
) -> tuple[ModelResponse, TokenUsage, dict[str, object] | None]:
    if not _response_is_truncated(response, initial_max_tokens):
        return response, TokenUsage.empty(), None
    retry_cap = min(max(1, configured_max_tokens), max(initial_max_tokens + 1, initial_max_tokens * 2))
    if retry_cap <= initial_max_tokens:
        return response, TokenUsage.empty(), None
    metadata: dict[str, object] = {
        "trigger": "finish_reason_length_or_incomplete_near_cap",
        "initial_max_tokens": initial_max_tokens,
        "retry_max_tokens": retry_cap,
        "attempted": True,
    }
    try:
        retried = _complete_with_optional_request_options(
            client,
            build_fireworks_answer_messages(task, domain=domain),
            temperature=temperature,
            max_tokens=retry_cap,
            request_options=request_options,
        )
    except _RequestOptionsFallback as fallback:
        retried = fallback.response
        metadata["request_options_fallback"] = fallback.reason
    except ModelClientError as exc:
        metadata["succeeded"] = False
        metadata["error"] = type(exc).__name__
        return response, TokenUsage.empty(), metadata
    metadata["succeeded"] = True
    return retried, retried.usage, metadata


def _response_is_truncated(response: ModelResponse, max_tokens: int) -> bool:
    choices = response.raw.get("choices") if isinstance(response.raw, dict) else None
    first = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    if str(first.get("finish_reason") or "").lower() == "length":
        return True
    if response.usage.completion < math.ceil(max_tokens * 0.95):
        return False
    text = response.text.rstrip()
    if not text or text.count("```") % 2:
        return True
    return text[-1] not in ".!?;:)}]`\"'"


def _completion_token_cap(task: TaskEnvelope, *, expected_format: str, tier: str, domain: str) -> int:
    text = task.input_text
    lowered = text.lower()
    if expected_format == "yes_no":
        return 64
    if expected_format == AnswerContractKind.LABEL.value:
        return 128
    if expected_format == "number":
        if domain == "math_reasoning" and tier == "strong":
            return 192
        if domain == "math_reasoning":
            return 128
        return 16
    if expected_format == "literal_echo":
        literal = extract_literal_echo(task)
        return _bounded_token_cap(_approx_tokens_for_chars(len(literal)) + 8, lower=16, upper=96)
    if expected_format == "uppercase":
        return _bounded_token_cap(_approx_tokens_for_chars(len(text)) + 16, lower=32, upper=160)
    if expected_format == "json":
        if infer_answer_contract(task).json_keys:
            return 256
        return _bounded_token_cap(_approx_tokens_for_chars(len(text)) + 96, lower=256, upper=384)
    if expected_format == "code":
        return 512

    explicit_word_cap = _explicit_word_cap(lowered)
    if explicit_word_cap is not None:
        return _bounded_token_cap(math.ceil(explicit_word_cap * 1.5) + 16, lower=32, upper=224)
    if re.search(r"\b(one|single)\s+(word|label|sentence)\b", lowered):
        return 96
    if re.search(
        r"\b(?:return|provide|answer with)\s+only\s+(?:the\s+)?(?:access\s+code|code|value|name|entity|word|answer)\b",
        lowered,
    ):
        return 64
    if re.search(r"\b(?:explain|compare|comparison|difference between|distinguish)\b", lowered):
        # Explanatory factual comparisons frequently need enough room to close a
        # final contrast or table. Keep the larger cap away from cheap
        # classification and non-factual domains, where it adds no value.
        if domain in {"general", "current_factual"} and tier != "cheap":
            return 384
        return 256
    if domain in {"classification", "formatting"} or tier == "cheap":
        return 128
    if domain == "extraction":
        return 384
    if domain == "summarization":
        return 256
    if domain == "logic":
        return 384
    if domain == "math_reasoning":
        return 192
    if tier == "strong":
        return 384
    if domain == "current_factual":
        return 256
    return 256


def _explicit_word_cap(lowered_text: str) -> int | None:
    patterns = [
        r"\b(?:at most|no more than|max(?:imum)?|under)\s+(\d{1,3})\s+words?\b",
        r"\bin\s+(\d{1,3})\s+words?\s+or\s+(?:fewer|less)\b",
        r"\b(\d{1,3})\s+words?\s+or\s+(?:fewer|less)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered_text)
        if match:
            return int(match.group(1))
    return None


def _approx_tokens_for_chars(chars: int) -> int:
    return max(1, math.ceil(chars / 4))


def _bounded_token_cap(value: int, *, lower: int, upper: int) -> int:
    return min(upper, max(lower, value))


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
