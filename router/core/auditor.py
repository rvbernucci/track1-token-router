from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from router.core.contracts import TaskEnvelope, TokenUsage
from router.core.fireworks import FireworksClient
from router.core.model_client import ModelClientError
from router.core.prompts import build_fireworks_audit_messages
from router.core.verifier import VerificationDecision


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


class FireworksAuditor:
    def __init__(
        self,
        client: FireworksClient,
        *,
        temperature: float = 0.0,
        max_tokens: int = 256,
    ) -> None:
        self.client = client
        self.temperature = temperature
        self.max_tokens = max_tokens

    def audit(
        self,
        task: TaskEnvelope,
        model_1_candidate_raw: str,
        model_2_alternative_raw: str,
        verification: VerificationDecision,
    ) -> AuditResult:
        started_at = perf_counter()
        try:
            response = self.client.complete(
                build_fireworks_audit_messages(
                    task,
                    model_1_candidate_raw,
                    model_2_alternative_raw,
                    verification,
                ),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except ModelClientError as exc:
            return AuditResult(
                decision=AuditDecision(
                    decision="approve",
                    answer="",
                    reason=f"Fireworks audit failed; using M2B fallback: {exc}",
                    parse_failed=False,
                ),
                raw_text="",
                latency_ms=_elapsed_ms(started_at),
                usage=TokenUsage.empty(),
            )

        return AuditResult(
            decision=parse_audit_decision(response.text),
            raw_text=response.text,
            latency_ms=_elapsed_ms(started_at),
            usage=response.usage,
        )


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

