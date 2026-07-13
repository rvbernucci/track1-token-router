from __future__ import annotations

import re
from time import perf_counter

from router.core.contracts import AnswerResult, TaskEnvelope, TokenUsage
from router.core.model_client import LocalModelClient, ModelClientError
from router.core.runner import TaskRunner
from router.core.tool_planner import TOOL_PLANNER_PROMPT_VERSION, build_tool_planner_messages
from router.orchestration.tool_executor import run_tool_route


TOOL_ROUTE_POLICY_VERSION = "e2b-deterministic-tool-route-v1"


class ToolAugmentedRunner:
    """Experimental fail-closed E2B planner backed by proof-carrying local tools."""

    def __init__(
        self,
        *,
        planner_client: LocalModelClient,
        fallback_runner: TaskRunner,
        enabled: bool = False,
        max_tokens: int = 384,
        minimum_remaining_ms: int = 15_000,
    ) -> None:
        if max_tokens < 1 or minimum_remaining_ms < 1:
            raise ValueError("Tool runner limits must be positive.")
        self.planner_client = planner_client
        self.fallback_runner = fallback_runner
        self.enabled = enabled
        self.max_tokens = max_tokens
        self.minimum_remaining_ms = minimum_remaining_ms

    def run(self, task: TaskEnvelope, *, remaining_ms: int | None = None) -> AnswerResult:
        if not self.enabled:
            return self._fallback(task, "policy_disabled")
        if remaining_ms is not None and remaining_ms < self.minimum_remaining_ms:
            return self._fallback(task, "deadline_guard")
        if not is_tool_planner_candidate(task.input_text):
            return self._fallback(task, "structural_prefilter_rejected")
        started = perf_counter()
        try:
            response = self.planner_client.complete(
                build_tool_planner_messages(task.input_text),
                temperature=0,
                max_tokens=self.max_tokens,
                extra_body={"max_completion_tokens": self.max_tokens},
            )
        except (ModelClientError, OSError, TimeoutError, ValueError) as exc:
            return self._fallback(task, f"planner_failure:{type(exc).__name__}")
        decision = run_tool_route(task, response.text)
        if not decision.accepted:
            return self._fallback(task, decision.reason)
        return AnswerResult(
            id=task.id,
            answer=decision.answer,
            route="e2b_tool_verified",
            remote_tokens=TokenUsage.empty(),
            metadata={
                "runner": "tool_augmented",
                "policy_version": TOOL_ROUTE_POLICY_VERSION,
                "planner_prompt_version": TOOL_PLANNER_PROMPT_VERSION,
                "planner_model": self.planner_client.model,
                "planner_local_tokens": response.usage.to_dict(),
                "latency_tool_route_ms": round((perf_counter() - started) * 1000),
                "tool_decision": decision.to_dict(),
            },
        )

    def _fallback(self, task: TaskEnvelope, reason: str) -> AnswerResult:
        result = self.fallback_runner.run(task)
        return AnswerResult(
            id=result.id,
            answer=result.answer,
            route=result.route,
            remote_tokens=result.remote_tokens,
            metadata={
                **result.metadata,
                "tool_route": {
                    "policy_version": TOOL_ROUTE_POLICY_VERSION,
                    "accepted": False,
                    "reason": reason,
                },
            },
        )


def is_tool_planner_candidate(prompt: str) -> bool:
    text = prompt.strip()
    if not text or len(text) > 4_000:
        return False
    inventory = bool(
        re.search(r"\b(?:inventory|stock|warehouse|depot)\b", text, re.I)
        and re.search(r"\b(?:sell|sold|restock|add)\w*\b", text, re.I)
        and len(re.findall(r"\d+(?:\.\d+)?", text)) >= 2
    )
    recipe = bool(
        re.search(r"\b(?:recipe|servings?|portions?|batch)\b", text, re.I)
        and re.search(r"\b(?:cost|price|per\s+cup)\b", text, re.I)
        and re.search(r"\d+\s*/\s*\d+", text)
    )
    calculator = bool(
        re.search(r"\b(?:calculate|compute|evaluate)\b", text, re.I)
        and re.search(r"[+*/()]|(?<=\d)\s*-\s*(?=\d)", text)
        and not re.search(r"\b(?:code|python|javascript|typescript|rust|sql)\b", text, re.I)
    )
    logic = bool(
        re.search(r"\b(?:shortest|tallest|youngest|oldest|lightest|heaviest)\b", text, re.I)
        and re.search(r"\b(?:than|older|younger|taller|shorter|lighter|heavier)\b", text, re.I)
    )
    return inventory or recipe or calculator or logic
