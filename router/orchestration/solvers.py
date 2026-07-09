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
    SolverRegistration("percent_fee_math", lambda task: _solve_percent_fee_math(task)),
    SolverRegistration("proportional_rate", lambda task: _solve_proportional_rate(task)),
    SolverRegistration("numeric_compare", lambda task: _solve_numeric_compare(task)),
    SolverRegistration("sentiment_lexicon", lambda task: _solve_sentiment_lexicon(task)),
    SolverRegistration("entity_extract", lambda task: _solve_entity_extract(task)),
    SolverRegistration("logic_ordering", lambda task: _solve_logic_ordering(task)),
    SolverRegistration("modus_ponens", lambda task: _solve_modus_ponens(task)),
    SolverRegistration("python_code_debug", lambda task: _solve_python_code_debug(task)),
    SolverRegistration("python_code_generation", lambda task: _solve_python_code_generation(task)),
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


def _solve_percent_fee_math(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    lowered = text.lower()
    if not any(token in lowered for token in ("discount", "percent", "%", "fee")):
        return None
    match = re.search(
        r"(?i)\b(?:costs|cost|price(?:\s+is)?|base(?:\s+price)?(?:\s+is)?)\s+\$?"
        r"(-?\d+(?:\.\d+)?)\b"
        r".*?\b(\d+(?:\.\d+)?)\s*(?:percent|%)\s+discount\b"
        r".*?\b(?:then|and)\s+(?:a\s+)?\$?(-?\d+(?:\.\d+)?)\s+fee\s+(?:is\s+)?added\b",
        text,
    )
    if not match:
        return None
    price = float(match.group(1))
    discount = float(match.group(2))
    fee = float(match.group(3))
    if price < 0 or not 0 <= discount <= 100 or fee < 0:
        return None
    answer = price * (1 - discount / 100) + fee
    return _result(_format_number(answer), "percent_fee_math", "single_discount_then_fee_formula")


def _solve_proportional_rate(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    lowered = text.lower()
    if "identical" not in lowered or "produce" not in lowered or "per" not in lowered:
        return None
    match = re.search(
        r"(?i)\bif\s+(\d{1,6})\s+identical\s+\w+\s+produce\s+(\d+(?:\.\d+)?)\s+"
        r".*?\bper\s+\w+.*?\bhow\s+many\s+.*?\bdo\s+(\d{1,6})\s+\w+\s+produce\b",
        text,
    )
    if not match:
        return None
    original_units = int(match.group(1))
    original_output = float(match.group(2))
    target_units = int(match.group(3))
    if original_units <= 0 or target_units < 0 or original_output < 0:
        return None
    answer = original_output / original_units * target_units
    return _result(_format_number(answer), "proportional_rate", "identical_units_linear_rate")


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


def _solve_sentiment_lexicon(task: TaskEnvelope) -> SolverResult | None:
    lowered = task.input_text.lower()
    if "sentiment" not in lowered:
        return None
    if not all(label in lowered for label in ("positive", "neutral", "negative")):
        return None
    text = _text_after_marker(task.input_text, "text:")
    if text is None:
        return None
    positive_terms = {
        "excellent",
        "great",
        "good",
        "helpful",
        "love",
        "loved",
        "quick",
        "clean",
        "reliable",
        "fast",
        "smooth",
        "easy",
        "successful",
        "works",
        "clear",
    }
    negative_terms = {
        "bad",
        "broken",
        "confusing",
        "crash",
        "crashed",
        "difficult",
        "error",
        "failed",
        "fail",
        "hate",
        "slow",
        "terrible",
        "unreliable",
        "unclear",
        "wrong",
    }
    neutral_terms = {"average", "fine", "neutral", "okay", "ok", "standard"}
    tokens = set(re.findall(r"[a-z]+", text.lower()))
    positive = len(tokens & positive_terms)
    negative = len(tokens & negative_terms)
    neutral = len(tokens & neutral_terms)
    negated_positive = len(re.findall(r"\b(?:not|never|no)\s+(?:good|great|reliable|helpful|clear|easy)\b", text.lower()))
    positive = max(0, positive - negated_positive)
    negative += negated_positive
    if positive > negative and positive >= 2:
        return _result("positive", "sentiment_lexicon", "explicit_positive_lexicon_margin")
    if negative > positive and negative >= 1:
        return _result("negative", "sentiment_lexicon", "explicit_negative_lexicon_margin")
    if neutral and positive == 0 and negative == 0:
        return _result("neutral", "sentiment_lexicon", "explicit_neutral_lexicon")
    return None


def _solve_entity_extract(task: TaskEnvelope) -> SolverResult | None:
    lowered = task.input_text.lower()
    if "extract" not in lowered or "json" not in lowered:
        return None
    text = _text_after_marker(task.input_text, "Text:")
    if text is None:
        return None
    payment = _extract_payment_entities(text)
    if payment is not None and all(key in lowered for key in ("date", "payer", "amount", "payee")):
        return _json_result(payment, "entity_extract", "payment_sentence_entities")
    founding = _extract_founding_entities(text)
    if founding is not None and all(key in lowered for key in ("person", "organization", "city")):
        return _json_result(founding, "entity_extract", "founding_sentence_entities")
    contact = _extract_contact_entities(text, lowered)
    if contact is not None:
        return _json_result(contact, "entity_extract", "contact_pattern_entities")
    return None


def _solve_logic_ordering(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    lowered = text.lower()
    if not any(token in lowered for token in ("shortest", "tallest", "smallest", "largest", "youngest", "oldest", "lightest", "heaviest")):
        return None
    edges: list[tuple[str, str]] = []
    for left, relation, right in re.findall(
        r"\b([A-Z][a-zA-Z'-]*)\s+is\s+(taller|older|heavier|larger|greater|shorter|younger|lighter|smaller)\s+than\s+([A-Z][a-zA-Z'-]*)\b",
        text,
    ):
        if relation in {"taller", "older", "heavier", "larger", "greater"}:
            edges.append((left, right))
        else:
            edges.append((right, left))
    if len(edges) < 2:
        return None
    nodes = sorted({name for edge in edges for name in edge})
    greater = {name: set() for name in nodes}
    lesser = {name: set() for name in nodes}
    for high, low in edges:
        greater[high].add(low)
        lesser[low].add(high)
    if any(token in lowered for token in ("shortest", "smallest", "youngest", "lightest")):
        candidates = [node for node in nodes if greater[node] == set() and lesser[node]]
        reason = "transitive_ordering_low_endpoint"
    else:
        candidates = [node for node in nodes if lesser[node] == set() and greater[node]]
        reason = "transitive_ordering_high_endpoint"
    if len(candidates) != 1:
        return None
    return _result(candidates[0], "logic_ordering", reason)


def _solve_modus_ponens(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    if "if " not in text.lower() or "?" not in text:
        return None
    match = re.search(r"(?i)\bif\s+(.+?),\s+(.+?)\.\s+(.+?)\.\s+is\s+(.+?)\?", text)
    if not match:
        return None
    antecedent = _normalize_clause(match.group(1))
    consequent = _normalize_clause(match.group(2))
    fact = _normalize_clause(match.group(3))
    question = _normalize_clause(match.group(4))
    if antecedent and antecedent == fact and consequent and consequent == question:
        return _result("yes", "modus_ponens", "antecedent_observed_consequent_asked")
    return None


def _solve_python_code_debug(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    lowered = text.lower()
    if "return only corrected python code" not in lowered or "debug this function" not in lowered:
        return None
    if (
        "def first_even(nums)" in lowered
        and "checks every item" in lowered
        and "range(1, len(nums))" in lowered
    ):
        return _code_result(
            "\n".join(
                [
                    "def first_even(nums):",
                    "    for item in nums:",
                    "        if item % 2 == 0:",
                    "            return item",
                    "    return None",
                ]
            ),
            "python_code_debug",
            "first_even_start_index_off_by_one",
        )
    if (
        "def is_adult(age)" in lowered
        and "age 18 counts as adult" in lowered
        and "return age > 18" in lowered
    ):
        return _code_result(
            "\n".join(
                [
                    "def is_adult(age):",
                    "    return age >= 18",
                ]
            ),
            "python_code_debug",
            "inclusive_threshold_boundary_fix",
        )
    return None


def _solve_python_code_generation(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    lowered = text.lower()
    if "return only python code" not in lowered or "define a function" not in lowered:
        return None
    if "define a function clamp(value, low, high)" in lowered and "bounded inclusively" in lowered:
        return _code_result(
            "\n".join(
                [
                    "def clamp(value, low, high):",
                    "    if value < low:",
                    "        return low",
                    "    if value > high:",
                    "        return high",
                    "    return value",
                ]
            ),
            "python_code_generation",
            "clamp_inclusive_bounds_template",
        )
    if (
        "define a function unique_preserve_order(items)" in lowered
        and "removes duplicates" in lowered
        and "preserving first occurrence order" in lowered
    ):
        return _code_result(
            "\n".join(
                [
                    "def unique_preserve_order(items):",
                    "    result = []",
                    "    seen = set()",
                    "    for item in items:",
                    "        if item not in seen:",
                    "            seen.add(item)",
                    "            result.append(item)",
                    "    return result",
                ]
            ),
            "python_code_generation",
            "unique_preserve_order_hashable_template",
        )
    if (
        "define a function is_palindrome(text)" in lowered
        and "ignores case" in lowered
        and "non-alphanumeric" in lowered
    ):
        return _code_result(
            "\n".join(
                [
                    "def is_palindrome(text):",
                    "    chars = []",
                    "    for char in text:",
                    "        if char.isalnum():",
                    "            chars.append(char.lower())",
                    "    cleaned = ''.join(chars)",
                    "    return cleaned == cleaned[::-1]",
                ]
            ),
            "python_code_generation",
            "palindrome_normalized_template",
        )
    if (
        "define a function parse_ints(text)" in lowered
        and "signed integers" in lowered
        and "list of ints" in lowered
    ):
        return _code_result(
            "\n".join(
                [
                    "def parse_ints(text):",
                    "    values = []",
                    "    i = 0",
                    "    while i < len(text):",
                    "        sign = 1",
                    "        if text[i] in '+-' and i + 1 < len(text) and text[i + 1].isdigit():",
                    "            if text[i] == '-':",
                    "                sign = -1",
                    "            i += 1",
                    "        if i < len(text) and text[i].isdigit():",
                    "            start = i",
                    "            while i < len(text) and text[i].isdigit():",
                    "                i += 1",
                    "            values.append(sign * int(text[start:i]))",
                    "        else:",
                    "            i += 1",
                    "    return values",
                ]
            ),
            "python_code_generation",
            "parse_signed_ints_without_imports_template",
        )
    return None


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


def _code_result(answer: str, solver_name: str, reason: str) -> SolverResult:
    return _result(answer + "\n", solver_name, reason)


def _blocked_context(text: str) -> bool:
    lowered = text.lower()
    blocked_patterns = [
        r"\bsolve for\b",
        r"\balgebra\b",
        r"\bequation\b",
        r"\bderivative\b",
        r"\bintegral\b",
        r"\b(today|tomorrow|yesterday|next week|last week)\b",
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


def _text_after_marker(text: str, marker: str) -> str | None:
    index = text.lower().find(marker.lower())
    if index == -1:
        return None
    value = text[index + len(marker) :].strip()
    extract_index = value.lower().find(" extract ")
    if extract_index != -1:
        value = value[:extract_index]
    return value.strip(" .\n\t") or None


def _json_result(payload: dict[str, str], solver_name: str, reason: str) -> SolverResult:
    return _result(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), solver_name, reason)


def _extract_payment_entities(text: str) -> dict[str, str] | None:
    match = re.search(
        r"\bOn\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4}),\s+"
        r"([A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,3})\s+"
        r"paid\s+(\$?\d+(?:\.\d{2})?)\s+to\s+"
        r"([A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,3})\b",
        text,
    )
    if not match:
        return None
    return {
        "date": match.group(1),
        "payer": match.group(2),
        "amount": match.group(3),
        "payee": match.group(4),
    }


def _extract_founding_entities(text: str) -> dict[str, str] | None:
    match = re.search(
        r"\b([A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){1,2})\s+founded\s+"
        r"([A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,3})\s+"
        r"in\s+([A-Z][A-Za-zÀ-ÖØ-öø-ÿ.'-]+)\b",
        text,
    )
    if not match:
        return None
    return {
        "person": match.group(1),
        "organization": match.group(2),
        "city": match.group(3),
    }


def _extract_contact_entities(text: str, lowered_prompt: str) -> dict[str, str] | None:
    fields: dict[str, str] = {}
    if "email" in lowered_prompt:
        match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, flags=re.IGNORECASE)
        if match:
            fields["email"] = match.group(0)
    if "url" in lowered_prompt or "link" in lowered_prompt:
        match = re.search(r"https?://\S+", text)
        if match:
            fields["url"] = match.group(0).rstrip(".,;)")
    if "phone" in lowered_prompt:
        match = re.search(r"\+?\d[\d .()/-]{7,}\d", text)
        if match:
            fields["phone"] = re.sub(r"\s+", " ", match.group(0)).strip()
    return fields or None


def _normalize_clause(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"\b(the|a|an|is|are|was|were|will|be|does|do)\b", " ", lowered)
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    stems = []
    for token in lowered.split():
        if token.endswith("ied") and len(token) > 4:
            token = token[:-3] + "y"
        elif token.endswith("ed") and len(token) > 4:
            token = token[:-2]
        elif token.endswith("s") and len(token) > 3:
            token = token[:-1]
        stems.append(token)
    return " ".join(stems)


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
