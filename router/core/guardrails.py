from __future__ import annotations

import re
from dataclasses import dataclass

from router.core.contracts import AnswerResult, TaskEnvelope
from router.core.logging import JsonlRunLogger
from router.core.runner import TaskRunner


@dataclass(frozen=True)
class GuardrailDecision:
    answer: str
    route: str
    reason: str


class GuardedRunner:
    def __init__(self, inner: TaskRunner, logger: JsonlRunLogger | None = None) -> None:
        self.inner = inner
        self.logger = logger

    def run(self, task: TaskEnvelope) -> AnswerResult:
        decision = evaluate_guardrail(task)
        if decision is None:
            return self.inner.run(task)

        result = AnswerResult(
            id=task.id,
            answer=decision.answer,
            route=decision.route,
            metadata={
                "runner": "guardrails",
                "reason": decision.reason,
            },
        )
        if self.logger:
            self.logger.log_result(
                task,
                result,
                extra={
                    "stage": "deterministic_guardrail",
                    "reason": decision.reason,
                },
            )
        return result


def evaluate_guardrail(task: TaskEnvelope) -> GuardrailDecision | None:
    text = task.input_text.strip()
    if not text:
        return GuardrailDecision(
            answer="No task provided.",
            route="guardrail_empty",
            reason="empty_input",
        )

    greeting = _simple_greeting(text)
    if greeting:
        return GuardrailDecision(
            answer=greeting,
            route="guardrail_greeting",
            reason="simple_greeting",
        )

    arithmetic = _simple_add_sub(text)
    if arithmetic is not None:
        return GuardrailDecision(
            answer=str(arithmetic),
            route="guardrail_arithmetic",
            reason="safe_add_sub_expression",
        )

    echo = _literal_echo(text)
    if echo is not None:
        return GuardrailDecision(
            answer=echo,
            route="guardrail_echo",
            reason="literal_echo_request",
        )

    return None


def _simple_greeting(text: str) -> str | None:
    normalized = re.sub(r"\s+", " ", text.strip().lower()).strip("!.? ")
    if normalized in {"hi", "hello", "hey", "ola", "olá", "bom dia", "boa tarde", "boa noite"}:
        return "Hello! How can I help?"
    return None


def _simple_add_sub(text: str) -> int | None:
    lowered = re.sub(r"\s+", " ", text.strip().lower())
    match = re.fullmatch(
        r"(?:what is|calculate|compute)?\s*"
        r"(-?\d{1,6})\s*([+-])\s*(-?\d{1,6})"
        r"\??(?:\s*return only (?:the )?number\.?)?",
        lowered,
    )
    if not match:
        return None
    left = int(match.group(1))
    operator = match.group(2)
    right = int(match.group(3))
    if operator == "+":
        return left + right
    return left - right


def _literal_echo(text: str) -> str | None:
    if "\n" in text:
        return None
    patterns = [
        r"(?i)\s*ignore\s+any\s+request\s+to\s+explain\.\s*(?:return|output|respond with)\s+exactly\s+(.+?)(?:\s+and nothing else)?[.!]?\s*",
        r"(?i)\s*(?:return|output|respond with)\s+exactly\s+this\s+string\s+and\s+nothing\s+else\s*:\s*(.+?)\s*[.!]?\s*",
        r"(?i)\s*(?:return|output|respond with)\s+exactly\s+(.+?)(?:\s+and nothing else)?[.!]?\s*",
    ]
    match = next((re.fullmatch(pattern, text) for pattern in patterns if re.fullmatch(pattern, text)), None)
    if match is None:
        return None
    value = match.group(1).strip()
    if len(value) > 200:
        return None
    return value.strip("\"'")
