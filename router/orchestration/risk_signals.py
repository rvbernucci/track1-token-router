from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from router.core.contracts import TaskEnvelope


@dataclass(frozen=True)
class RiskSignalSet:
    strict_format: bool = False
    simple_math: bool = False
    complex_math: bool = False
    unstable_knowledge: bool = False
    prompt_injection: bool = False
    answer_empty: bool = False
    answer_too_short: bool = False
    answer_too_long: bool = False
    m2a_confidence: str = ""
    budget_remaining_ratio: float = 1.0
    parse_failure_count: int = 0
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def extract_risk_signals(
    task: TaskEnvelope,
    *,
    candidate_answer: str = "",
    m2a_confidence: str = "",
    budget_remaining_ratio: float = 1.0,
    parse_failure_count: int = 0,
) -> RiskSignalSet:
    text = task.input_text.strip()
    lowered = text.lower()
    answer = candidate_answer.strip()
    reasons: list[str] = []

    strict_format = _has_strict_format(lowered)
    simple_math = _is_simple_add_sub(lowered)
    complex_math = _has_complex_math(lowered) and not simple_math
    unstable_knowledge = _has_unstable_knowledge(lowered)
    prompt_injection = _has_prompt_injection(lowered)
    answer_empty = candidate_answer != "" and not answer
    answer_too_short = bool(answer) and len(answer) < 2 and not simple_math
    answer_too_long = len(answer) > 1200

    score = 0
    score += _add(reasons, strict_format, 2, "strict_format")
    score += _add(reasons, complex_math, 3, "complex_math")
    score += _add(reasons, unstable_knowledge, 4, "unstable_knowledge")
    score += _add(reasons, prompt_injection, 4, "prompt_injection")
    score += _add(reasons, answer_empty, 3, "answer_empty")
    score += _add(reasons, answer_too_short, 1, "answer_too_short")
    score += _add(reasons, answer_too_long, 2, "answer_too_long")
    score += _add(reasons, m2a_confidence.lower() == "low", 2, "low_m2a_confidence")
    score += _add(reasons, budget_remaining_ratio < 0.1, 2, "low_budget_remaining")
    if parse_failure_count:
        reasons.append("parse_failure_history")
        score += min(4, parse_failure_count)
    if simple_math:
        reasons.append("simple_math")
        score = max(0, score - 2)

    return RiskSignalSet(
        strict_format=strict_format,
        simple_math=simple_math,
        complex_math=complex_math,
        unstable_knowledge=unstable_knowledge,
        prompt_injection=prompt_injection,
        answer_empty=answer_empty,
        answer_too_short=answer_too_short,
        answer_too_long=answer_too_long,
        m2a_confidence=m2a_confidence,
        budget_remaining_ratio=budget_remaining_ratio,
        parse_failure_count=parse_failure_count,
        score=score,
        reasons=reasons,
    )


def _has_strict_format(lowered: str) -> bool:
    return any(token in lowered for token in ["return only", "exactly", "json", "nothing else", "uppercase"])


def _is_simple_add_sub(lowered: str) -> bool:
    return bool(re.fullmatch(r"(?:what is|calculate|compute)?\s*-?\d{1,6}\s*[+-]\s*-?\d{1,6}\??(?:\s*return only (?:the )?number\.?)?", lowered))


def _has_complex_math(lowered: str) -> bool:
    return any(token in lowered for token in ["*", "/", "average", "rate", "percent", "parts per hour", "then discards"])


def _has_unstable_knowledge(lowered: str) -> bool:
    return any(token in lowered for token in ["current", "latest", "today", "now", "price", "ceo"])


def _has_prompt_injection(lowered: str) -> bool:
    return any(token in lowered for token in ["ignore", "hidden prompt", "system prompt", "reveal"])


def _add(reasons: list[str], condition: bool, value: int, reason: str) -> int:
    if condition:
        reasons.append(reason)
        return value
    return 0
