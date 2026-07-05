from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from router.core.contracts import TaskEnvelope, TokenUsage
from router.core.model_client import LocalModelClient
from router.core.prompts import build_m2b_messages
from router.core.verifier import VerificationDecision


@dataclass(frozen=True)
class RepairResult:
    answer: str
    latency_ms: int
    usage: TokenUsage


class LocalRepairGenerator:
    def __init__(
        self,
        client: LocalModelClient,
        *,
        temperature: float = 0.2,
        max_tokens: int = 768,
    ) -> None:
        self.client = client
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(
        self,
        task: TaskEnvelope,
        model_1_candidate_raw: str,
        verification: VerificationDecision,
    ) -> RepairResult:
        started_at = perf_counter()
        response = self.client.complete(
            build_m2b_messages(task, model_1_candidate_raw, verification),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return RepairResult(
            answer=response.text,
            latency_ms=round((perf_counter() - started_at) * 1000),
            usage=response.usage,
        )

