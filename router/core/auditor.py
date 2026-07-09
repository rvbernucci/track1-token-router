from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any

from router.core.contracts import TaskEnvelope, TokenUsage
from router.core.fireworks import FireworksClient
from router.core.model_client import ModelClientError
from router.core.prompts import build_fireworks_audit_messages
from router.core.verifier import VerificationDecision
from router.orchestration.fireworks_model_router import select_fireworks_model, select_reasoning_effort
from router.orchestration.matrix_regression_selector import (
    MatrixRegressionWeights,
    load_weights,
    select_model_by_matrix_regression,
)


@dataclass(frozen=True)
class AuditDecision:
    decision: str
    answer: str = ""
    reason: str = ""
    parse_failed: bool = False

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "AuditDecision":
        raw_decision = str(payload.get("decision") or "").strip().lower()
        decision = "approve" if raw_decision == "approve" else "replace"
        return cls(
            decision=decision,
            answer=str(payload.get("answer") or ""),
            reason=str(payload.get("reason") or ""),
            parse_failed=False,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "answer": self.answer,
            "reason": self.reason,
            "parse_failed": self.parse_failed,
        }


@dataclass(frozen=True)
class AuditResult:
    decision: AuditDecision
    raw_text: str
    latency_ms: int
    usage: TokenUsage
    metadata: dict[str, Any] = field(default_factory=dict)


class FireworksAuditor:
    def __init__(
        self,
        client: FireworksClient,
        *,
        temperature: float = 0.0,
        max_tokens: int = 256,
        allowed_models: list[str] | None = None,
        service_tier: str | None = None,
        matrix_weights_path: Path | None = None,
    ) -> None:
        self.client = client
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.allowed_models = allowed_models or []
        self.service_tier = service_tier
        self.matrix_weights_path = matrix_weights_path
        self._matrix_weights: MatrixRegressionWeights | None = None
        self._matrix_error: str | None = None
        self._unavailable_models: set[str] = set()

    def audit(
        self,
        task: TaskEnvelope,
        model_1_candidate_raw: str,
        model_2_alternative_raw: str,
        verification: VerificationDecision,
    ) -> AuditResult:
        started_at = perf_counter()
        messages = build_fireworks_audit_messages(
            task,
            model_1_candidate_raw,
            model_2_alternative_raw,
            verification,
        )
        selection = select_fireworks_model(task, self.allowed_models, default_model=self.client.model)
        matrix_selection = self._matrix_selection(task)
        selected_model = str(matrix_selection.get("model") or selection.model) if matrix_selection else selection.model
        request_options: dict[str, object] = {}
        request_options_fallback: str | None = None
        attempt_errors: list[dict[str, str]] = []
        original_model = self.client.model
        response_text = ""
        response_usage = TokenUsage.empty()
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
                        messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        request_options=request_options,
                    )
                    response_text = response.text
                    response_usage = response.usage
                    break
                except _RequestOptionsFallback as fallback:
                    response_text = fallback.response.text
                    response_usage = fallback.response.usage
                    request_options_fallback = fallback.reason
                    break
                except ModelClientError as exc:
                    error = str(exc)
                    attempt_errors.append({"model": selected_model, "error": error})
                    if _is_unavailable_model_error(error):
                        self._unavailable_models.add(selected_model)
                    continue
        finally:
            self.client.model = original_model

        metadata = {
            "fireworks_model": selected_model,
            "fireworks_model_selection": selection.to_dict(),
            "fireworks_matrix_selection": matrix_selection,
            "fireworks_request_options": request_options,
            "fireworks_request_options_fallback": request_options_fallback,
            "fireworks_attempt_errors": attempt_errors,
            "fireworks_unavailable_models": sorted(self._unavailable_models),
        }

        if not response_text:
            return AuditResult(
                decision=AuditDecision(
                    decision="approve",
                    answer="",
                    reason=(
                        "Fireworks audit failed; using M2B fallback: "
                        + (attempt_errors[-1]["error"] if attempt_errors else "no_model_attempted")
                    ),
                    parse_failed=False,
                ),
                raw_text="",
                latency_ms=_elapsed_ms(started_at),
                usage=TokenUsage.empty(),
                metadata=metadata,
            )

        return AuditResult(
            decision=parse_audit_decision(response_text),
            raw_text=response_text,
            latency_ms=_elapsed_ms(started_at),
            usage=response_usage,
            metadata=metadata,
        )

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


def parse_audit_decision(raw_text: str) -> AuditDecision:
    try:
        payload = json.loads(_extract_json_object(raw_text))
    except (ValueError, json.JSONDecodeError) as exc:
        return AuditDecision(
            decision="replace",
            answer=raw_text,
            reason=f"Fireworks emitted invalid JSON: {exc}",
            parse_failed=True,
        )
    if not isinstance(payload, dict):
        return AuditDecision(
            decision="replace",
            answer=raw_text,
            reason="Fireworks JSON was not an object.",
            parse_failed=True,
        )
    return AuditDecision.from_mapping(payload)


def _extract_json_object(raw_text: str) -> str:
    stripped = raw_text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found.")
    return stripped[start : end + 1]


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
) -> Any:
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


class _RequestOptionsFallback(Exception):
    def __init__(self, response: Any, reason: str) -> None:
        super().__init__(reason)
        self.response = response
        self.reason = reason
