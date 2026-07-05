from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Callable

from router.core.contracts import TaskEnvelope


@dataclass(frozen=True)
class SolverResult:
    answer: str
    solver_name: str
    confidence: str
    reason: str

    @property
    def route(self) -> str:
        return f"solver_{self.solver_name}"

    def to_dict(self) -> dict[str, str]:
        payload = asdict(self)
        payload["route"] = self.route
        return payload


@dataclass(frozen=True)
class SolverRegistration:
    name: str
    solve: Callable[[TaskEnvelope], SolverResult | None]


SOLVERS: tuple[SolverRegistration, ...] = (
    SolverRegistration("arithmetic", lambda task: _solve_arithmetic(task)),
    SolverRegistration("numeric_compare", lambda task: _solve_numeric_compare(task)),
    SolverRegistration("char_count", lambda task: _solve_char_count(task)),
    SolverRegistration("word_count", lambda task: _solve_word_count(task)),
    SolverRegistration("case_transform", lambda task: _solve_case_transform(task)),
    SolverRegistration("whitespace", lambda task: _solve_whitespace(task)),
    SolverRegistration("json_transform", lambda task: _solve_json_transform(task)),
    SolverRegistration("list_item", lambda task: _solve_list_item(task)),
)


def solve_deterministic(task: TaskEnvelope) -> SolverResult | None:
    if _blocked_context(task.input_text):
        return None
    for registration in SOLVERS:
        result = registration.solve(task)
        if result is not None:
            return result
    return None


def _solve_arithmetic(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    match = re.fullmatch(
        r"(?i)(?:what is|calculate|compute|solve)?\s*"
        r"(-?\d{1,9})\s*([+\-*/])\s*(-?\d{1,9})"
        r"\??(?:\s*return only (?:the )?number\.?)?",
        text,
    )
    if not match:
        return None
    left = int(match.group(1))
    operator = match.group(2)
    right = int(match.group(3))
    if operator == "+":
        answer = left + right
    elif operator == "-":
        answer = left - right
    elif operator == "*":
        answer = left * right
    else:
        if right == 0 or left % right != 0:
            return None
        answer = left // right
    return _result(str(answer), "arithmetic", "safe_fullmatch_integer_arithmetic")


def _solve_numeric_compare(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    lowered = text.lower()
    if not any(token in lowered for token in ("larger", "greater", "maximum", "max", "smaller", "lower", "minimum", "min")):
        return None
    numbers = re.findall(r"-?\d+(?:\.\d+)?", text)
    if len(numbers) != 2:
        return None
    left = float(numbers[0])
    right = float(numbers[1])
    choose_max = any(token in lowered for token in ("larger", "greater", "maximum", "max"))
    chosen = max(left, right) if choose_max else min(left, right)
    return _result(_format_number(chosen), "numeric_compare", "exactly_two_numbers_with_compare_keyword")


def _solve_char_count(task: TaskEnvelope) -> SolverResult | None:
    lowered = task.input_text.lower()
    if "character" not in lowered and "chars" not in lowered:
        return None
    value = _quoted_value(task.input_text)
    if value is None:
        return None
    return _result(str(len(value)), "char_count", "quoted_string_character_count")


def _solve_word_count(task: TaskEnvelope) -> SolverResult | None:
    lowered = task.input_text.lower()
    if "word" not in lowered:
        return None
    value = _quoted_value(task.input_text)
    if value is None:
        return None
    count = len(re.findall(r"\b[\w'-]+\b", value, flags=re.UNICODE))
    return _result(str(count), "word_count", "quoted_string_word_count")


def _solve_case_transform(task: TaskEnvelope) -> SolverResult | None:
    lowered = task.input_text.lower()
    value = _quoted_value(task.input_text)
    if value is None:
        return None
    if "uppercase" in lowered or "upper case" in lowered:
        return _result(value.upper(), "case_transform", "quoted_uppercase_transform")
    if "lowercase" in lowered or "lower case" in lowered:
        return _result(value.lower(), "case_transform", "quoted_lowercase_transform")
    if "titlecase" in lowered or "title case" in lowered:
        return _result(value.title(), "case_transform", "quoted_titlecase_transform")
    return None


def _solve_whitespace(task: TaskEnvelope) -> SolverResult | None:
    lowered = task.input_text.lower()
    value = _quoted_value(task.input_text)
    if value is None:
        return None
    if "normalize whitespace" in lowered or "collapse whitespace" in lowered:
        return _result(re.sub(r"\s+", " ", value).strip(), "whitespace", "quoted_whitespace_normalization")
    if "trim whitespace" in lowered or "strip whitespace" in lowered:
        return _result(value.strip(), "whitespace", "quoted_whitespace_trim")
    return None


def _solve_json_transform(task: TaskEnvelope) -> SolverResult | None:
    lowered = task.input_text.lower()
    if "json" not in lowered:
        return None
    payload = _extract_json_payload(task.input_text)
    if payload is None:
        return None
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if "compact" in lowered or "minify" in lowered:
        answer = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return _result(answer, "json_transform", "valid_json_compact_transform")
    if "pretty" in lowered or "format json" in lowered:
        answer = json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True)
        return _result(answer, "json_transform", "valid_json_pretty_transform")
    return None


def _solve_list_item(task: TaskEnvelope) -> SolverResult | None:
    lowered = task.input_text.lower()
    if "first item" not in lowered and "last item" not in lowered:
        return None
    items = _extract_list_items(task.input_text)
    if not items:
        return None
    answer = items[0] if "first item" in lowered else items[-1]
    return _result(answer, "list_item", "simple_list_boundary_extraction")


def _result(answer: str, solver_name: str, reason: str) -> SolverResult:
    return SolverResult(
        answer=answer,
        solver_name=solver_name,
        confidence="high",
        reason=reason,
    )


def _blocked_context(text: str) -> bool:
    lowered = text.lower()
    blocked_patterns = [
        r"\bsolve for\b",
        r"\balgebra\b",
        r"\bequation\b",
        r"\bderivative\b",
        r"\bintegral\b",
        r"\b(today|tomorrow|yesterday|next week|last week|date)\b",
        r"\bparts per hour\b",
        r"\baverage speed\b",
        r"\btravels?\b",
        r"\bworkshop\b",
        r"\bsort(?:ing|ed)?\b",
    ]
    return any(re.search(pattern, lowered) for pattern in blocked_patterns)


def _single_line(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return str(value).rstrip("0").rstrip(".")


def _quoted_value(text: str) -> str | None:
    match = re.search(r'"([^"]*)"', text, flags=re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r"'([^']*)'", text, flags=re.DOTALL)
    if match:
        return match.group(1)
    return None


def _extract_json_payload(text: str) -> str | None:
    candidates = []
    for open_char, close_char in (("{", "}"), ("[", "]")):
        start = text.find(open_char)
        end = text.rfind(close_char)
        if start != -1 and end > start:
            candidates.append(text[start : end + 1])
    if not candidates:
        return None
    return min(candidates, key=len)


def _extract_list_items(text: str) -> list[str]:
    payload = _extract_json_payload(text)
    if payload is not None:
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list) and all(isinstance(item, (str, int, float)) for item in parsed):
            return [str(item) for item in parsed]

    match = re.search(r":\s*(.+)$", text, flags=re.DOTALL)
    if not match:
        return []
    raw_items = [item.strip() for item in match.group(1).split(",")]
    items = [item.strip("\"' ") for item in raw_items if item.strip()]
    if 1 <= len(items) <= 20:
        return items
    return []
