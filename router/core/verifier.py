from __future__ import annotations

import json
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from router.core.contracts import TaskEnvelope, TokenUsage
from router.core.model_client import LocalModelClient, ModelClientError
from router.core.prompts import build_m2a_messages


@dataclass(frozen=True)
class VerificationDecision:
    decision: str
    confidence: str = "low"
    reason: str = ""
    failure_modes: list[str] = field(default_factory=list)
    should_generate_alternative: bool = False

    @classmethod
    def approve(cls, reason: str = "Candidate is sufficient.") -> "VerificationDecision":
        return cls(
            decision="approve",
            confidence="high",
            reason=reason,
            failure_modes=[],
            should_generate_alternative=False,
        )

    @classmethod
    def escalate(cls, reason: str, failure_modes: list[str] | None = None) -> "VerificationDecision":
        return cls(
            decision="escalate",
            confidence="low",
            reason=reason,
            failure_modes=failure_modes or ["verification_risk"],
            should_generate_alternative=True,
        )

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "VerificationDecision":
        raw_decision = str(payload.get("decision", "")).strip().lower()
        decision = "approve" if raw_decision == "approve" else "escalate"
        raw_failure_modes = payload.get("failure_modes") or []
        failure_modes = [str(item) for item in raw_failure_modes] if isinstance(raw_failure_modes, list) else []
        return cls(
            decision=decision,
            confidence=str(payload.get("confidence") or "low"),
            reason=str(payload.get("reason") or ""),
            failure_modes=failure_modes,
            should_generate_alternative=bool(payload.get("should_generate_alternative", decision == "escalate")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "reason": self.reason,
            "failure_modes": self.failure_modes,
            "should_generate_alternative": self.should_generate_alternative,
        }


@dataclass(frozen=True)
class VerificationResult:
    decision: VerificationDecision
    raw_text: str
    latency_ms: int
    usage: TokenUsage


class LocalVerifier:
    def __init__(
        self,
        client: LocalModelClient,
        *,
        temperature: float = 0.0,
        max_tokens: int = 256,
    ) -> None:
        self.client = client
        self.temperature = temperature
        self.max_tokens = max_tokens

    def verify(self, task: TaskEnvelope, model_1_candidate_raw: str) -> VerificationResult:
        started_at = perf_counter()
        try:
            response = self.client.complete(
                build_m2a_messages(task, model_1_candidate_raw),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except ModelClientError as exc:
            return VerificationResult(
                decision=VerificationDecision.escalate(
                    reason=f"Verifier call failed: {exc}",
                    failure_modes=["verifier_error"],
                ),
                raw_text="",
                latency_ms=_elapsed_ms(started_at),
                usage=TokenUsage.empty(),
            )

        return VerificationResult(
            decision=parse_verification_decision(response.text),
            raw_text=response.text,
            latency_ms=_elapsed_ms(started_at),
            usage=response.usage,
        )


def parse_verification_decision(raw_text: str) -> VerificationDecision:
    try:
        payload = json.loads(_extract_json_object(raw_text))
    except (ValueError, json.JSONDecodeError) as exc:
        return VerificationDecision.escalate(
            reason=f"Verifier emitted invalid JSON: {exc}",
            failure_modes=["invalid_verifier_json"],
        )
    if not isinstance(payload, dict):
        return VerificationDecision.escalate(
            reason="Verifier JSON was not an object.",
            failure_modes=["invalid_verifier_schema"],
        )
    return VerificationDecision.from_mapping(payload)


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

