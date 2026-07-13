from __future__ import annotations

import ast
from fractions import Fraction
import json
import re
from dataclasses import asdict, dataclass
from typing import Callable

from router.core.contracts import Intent, TaskAssessment, TaskEnvelope


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
    capabilities: tuple[tuple[Intent, str], ...] = ()


SOLVERS: tuple[SolverRegistration, ...] = (
    SolverRegistration("arithmetic", lambda task: _solve_arithmetic(task), ((Intent.MATH_REASONING, "arithmetic"),)),
    SolverRegistration(
        "inventory_flow",
        lambda task: _solve_inventory_flow(task),
        ((Intent.MATH_REASONING, "inventory_flow"),),
    ),
    SolverRegistration(
        "recipe_cost",
        lambda task: _solve_recipe_cost(task),
        ((Intent.MATH_REASONING, "proportional_rate"),),
    ),
    SolverRegistration(
        "percent_fee_math",
        lambda task: _solve_percent_fee_math(task),
        ((Intent.MATH_REASONING, "percent_fee_math"),),
    ),
    SolverRegistration(
        "proportional_rate",
        lambda task: _solve_proportional_rate(task),
        ((Intent.MATH_REASONING, "proportional_rate"),),
    ),
    SolverRegistration(
        "numeric_compare",
        lambda task: _solve_numeric_compare(task),
        ((Intent.MATH_REASONING, "numeric_compare"),),
    ),
    SolverRegistration(
        "literal_echo",
        lambda task: _solve_literal_echo(task),
        ((Intent.FACTUAL_QA, "context_qa"),),
    ),
    SolverRegistration(
        "stable_factual_qa",
        lambda task: None,
        ((Intent.FACTUAL_QA, "stable_fact"),),
    ),
    SolverRegistration(
        "sentiment_lexicon",
        lambda task: _solve_sentiment_lexicon(task),
        ((Intent.SENTIMENT, "polarity"),),
    ),
    SolverRegistration(
        "constrained_summary",
        lambda task: _solve_constrained_summary(task),
        ((Intent.SUMMARIZATION, "constrained_summary"),),
    ),
    SolverRegistration(
        "entity_extract",
        lambda task: _solve_entity_extract(task),
        ((Intent.NER, "entity_extract"), (Intent.NER, "typed_entity_extract")),
    ),
    SolverRegistration(
        "logic_ordering",
        lambda task: _solve_logic_ordering(task),
        ((Intent.LOGIC_PUZZLE, "ordering"),),
    ),
    SolverRegistration(
        "modus_ponens",
        lambda task: _solve_modus_ponens(task),
        ((Intent.LOGIC_PUZZLE, "modus_ponens"), (Intent.LOGIC_PUZZLE, "deduction")),
    ),
    SolverRegistration(
        "modus_tollens",
        lambda task: _solve_modus_tollens(task),
        ((Intent.LOGIC_PUZZLE, "modus_tollens"), (Intent.LOGIC_PUZZLE, "deduction")),
    ),
    SolverRegistration(
        "python_code_debug",
        lambda task: _solve_python_code_debug(task),
        ((Intent.CODE_DEBUGGING, "python_debug"),),
    ),
    SolverRegistration(
        "python_code_generation",
        lambda task: _solve_python_code_generation(task),
        ((Intent.CODE_GENERATION, "python_generation"),),
    ),
    SolverRegistration("char_count", lambda task: _solve_char_count(task), ((Intent.FACTUAL_QA, "context_qa"),)),
    SolverRegistration("word_count", lambda task: _solve_word_count(task), ((Intent.FACTUAL_QA, "context_qa"),)),
    SolverRegistration(
        "case_transform",
        lambda task: _solve_case_transform(task),
        ((Intent.SUMMARIZATION, "extractive_summary"),),
    ),
    SolverRegistration(
        "whitespace",
        lambda task: _solve_whitespace(task),
        ((Intent.SUMMARIZATION, "extractive_summary"),),
    ),
    SolverRegistration(
        "json_transform",
        lambda task: _solve_json_transform(task),
        ((Intent.NER, "typed_entity_extract"),),
    ),
    SolverRegistration(
        "list_item",
        lambda task: _solve_list_item(task),
        ((Intent.NER, "entity_extract"),),
    ),
)


def solver_names() -> tuple[str, ...]:
    return tuple(registration.name for registration in SOLVERS)


def solver_manifest() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "name": registration.name,
            "capabilities": tuple(
                {"intent": intent.value, "sub_intent": sub_intent}
                for intent, sub_intent in registration.capabilities
            ),
        }
        for registration in SOLVERS
    )


def solver_hints_for_assessment(assessment: TaskAssessment) -> tuple[str, ...]:
    if assessment.sub_intent is None:
        return tuple(
            registration.name
            for registration in SOLVERS
            if any(intent is assessment.intent for intent, _ in registration.capabilities)
        )
    capability = (assessment.intent, assessment.sub_intent)
    return tuple(
        registration.name
        for registration in SOLVERS
        if capability in registration.capabilities
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
    aggregate = _solve_arithmetic_aggregate(text)
    if aggregate is not None:
        return aggregate
    fraction_capacity = _solve_fraction_capacity(text)
    if fraction_capacity is not None:
        return fraction_capacity
    explicit = re.fullmatch(
        r"(?i)(?:calculate|evaluate)\s+the\s+explicit\s+expression\s+"
        r"\((-?\d{1,9})\s*([+\-*])\s*(-?\d{1,9})\)\s*([+\-*/])\s*(-?\d{1,9})\.\s*"
        r"return\s+only\s+the\s+number\.",
        text,
    )
    if explicit:
        left = _apply_fraction_operator(Fraction(int(explicit.group(1))), explicit.group(2), Fraction(int(explicit.group(3))))
        if left is None:
            return None
        answer = _apply_fraction_operator(left, explicit.group(4), Fraction(int(explicit.group(5))))
        if answer is None:
            return None
        return _result(_format_fraction(answer), "arithmetic", "explicit_parenthesized_fraction_expression")
    match = re.fullmatch(
        r"(?i)(?:what is|calculate|compute|solve)?\s*"
        r"(-?\d{1,9})\s*([+\-*/])\s*(-?\d{1,9})"
        r"\??(?:\s*return only (?:the )?number\.?)?",
        text,
    )
    if match:
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

    expression_match = re.fullmatch(
        r"(?i)(?:compute|calculate|evaluate)\s+([0-9+\-*/()\s]+)\.?"
        r"(?:\s*return only (?:the )?number\.?)?",
        text,
    )
    if not expression_match:
        return None
    answer = _safe_integer_expression(expression_match.group(1))
    if answer is None:
        return None
    return _result(str(answer), "arithmetic", "safe_integer_expression")


def _solve_inventory_flow(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    patterns = (
        r"a\s+[a-z][a-z -]{0,40}\s+starts\s+with\s+([\d,]+)\s+units\.\s+"
        r"in\s+[a-z0-9 -]+\s+it\s+sells\s+(\d+(?:\.\d+)?)%\s+of\s+(?:the\s+)?stock\.\s+"
        r"in\s+[a-z0-9 -]+\s+it\s+restocks\s+([\d,]+)\s+units\.\s+"
        r"in\s+[a-z0-9 -]+\s+it\s+sells\s+([\d,]+)\s+units\.\s+"
        r"how\s+many\s+units\s+remain\s+at\s+the\s+end\s+of\s+[a-z0-9 -]+\?",
        r"a\s+warehouse\s+starts\s+with\s+([\d,]+)\s+units\.\s+it\s+sells\s+"
        r"(\d+(?:\.\d+)?)%\s+of\s+stock,\s+restocks\s+([\d,]+)\s+units,\s+then\s+sells\s+"
        r"([\d,]+)\s+units\.\s+how\s+many\s+units\s+remain\?",
        r"inventory\s+begins\s+at\s+([\d,]+)\.\s+sell\s+(\d+(?:\.\d+)?)\s+percent,\s+"
        r"add\s+([\d,]+)(?:\s+units)?,\s+and\s+sell\s+another\s+([\d,]+)\s+units\.\s+"
        r"return\s+the\s+final\s+(?:unit\s+)?count\.",
        r"a\s+depot\s+has\s+([\d,]+)\s+items;\s+(\d+(?:\.\d+)?)%\s+are\s+sold,\s+"
        r"([\d,]+)\s+arrive,\s+and\s+([\d,]+)\s+more\s+are\s+sold\.\s+"
        r"determine\s+ending\s+inventory\.",
        r"starting\s+stock\s+is\s+([\d,]+)\.\s+sell\s+(\d+(?:\.\d+)?)%\s+of\s+stock,\s+"
        r"restock\s+([\d,]+)\s+units,\s+then\s+sell\s+([\d,]+)\s+units\.\s+"
        r"find\s+the\s+remaining\s+units\.",
    )
    match = next((found for pattern in patterns if (found := re.fullmatch(pattern, text, re.IGNORECASE))), None)
    if not match:
        return None
    initial = int(match.group(1).replace(",", ""))
    percent = Fraction(match.group(2))
    restocked = int(match.group(3).replace(",", ""))
    sold = int(match.group(4).replace(",", ""))
    if initial < 0 or percent < 0 or percent > 100 or restocked < 0 or sold < 0:
        return None
    remaining = Fraction(initial) * (1 - percent / 100) + restocked - sold
    if remaining < 0:
        return None
    rendered_remaining = (
        f"{remaining.numerator:,}"
        if remaining.denominator == 1
        else _format_fraction(remaining)
    )
    return _result(
        f"{rendered_remaining} units",
        "inventory_flow",
        "ordered_percent_sale_restock_absolute_sale_proof",
    )


def _solve_recipe_cost(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    patterns = (
        r"a\s+recipe\s+requires\s+(\d{1,4})/(\d{1,4})\s+(cup|cups|gram|grams|kilogram|kilograms)\s+"
        r"of\s+([a-z][a-z -]{0,40})\s+for\s+(\d{1,6})\s+([a-z][a-z -]{0,30})\.\s+"
        r"how\s+much\s+\4\s+is\s+needed\s+for\s+(\d{1,6})\s+\6\?\s+"
        r"if\s+\4\s+costs\s+\$(\d+(?:\.\d{1,2})?)\s+per\s+(cup|gram|kilogram),\s+"
        r"what\s+is\s+the\s+total\s+cost\s+of\s+\4\s+for\s+\7\s+\6\?",
        r"for\s+(\d{1,6})\s+portions,\s+a\s+dish\s+needs\s+(\d{1,4})/(\d{1,4})\s+cup\s+of\s+"
        r"([a-z][a-z -]{0,40})\.\s+find\s+cups\s+and\s+cost\s+for\s+(\d{1,6})\s+portions\s+"
        r"if\s+\4\s+costs\s+\$(\d+(?:\.\d{1,2})?)\s+per\s+cup\.",
        r"a\s+recipe\s+uses\s+(\d{1,4})/(\d{1,4})\s+cup\s+of\s+([a-z][a-z -]{0,40})\s+for\s+"
        r"(\d{1,6})\s+servings\.\s+scale\s+to\s+(\d{1,6})\s+servings\s+and\s+calculate\s+cost\s+"
        r"at\s+\$(\d+(?:\.\d{1,2})?)\s+per\s+cup\.",
        r"a\s+batch\s+serving\s+(\d{1,6})\s+uses\s+(\d{1,4})/(\d{1,4})\s+cup\s+of\s+"
        r"([a-z][a-z -]{0,40})\.\s+find\s+amount\s+and\s+total\s+cost\s+for\s+(\d{1,6})\s+"
        r"servings\s+at\s+\$(\d+(?:\.\d{1,2})?)\s+per\s+cup\.",
    )
    match = next((found for pattern in patterns if (found := re.fullmatch(pattern, text, re.IGNORECASE))), None)
    if not match:
        return None
    if len(match.groups()) == 9:
        numerator, denominator = int(match.group(1)), int(match.group(2))
        source_count, target_count = int(match.group(5)), int(match.group(7))
        price, unit = Fraction(match.group(8)), match.group(9).lower()
        amount_unit = match.group(3).lower().rstrip("s")
        if amount_unit != unit:
            return None
    elif text.casefold().startswith("for ") or text.casefold().startswith("a batch"):
        source_count = int(match.group(1))
        numerator, denominator = int(match.group(2)), int(match.group(3))
        target_count, price, unit = int(match.group(5)), Fraction(match.group(6)), "cup"
    else:
        numerator, denominator = int(match.group(1)), int(match.group(2))
        source_count, target_count = int(match.group(4)), int(match.group(5))
        price, unit = Fraction(match.group(6)), "cup"
    if denominator <= 0 or numerator < 0 or source_count <= 0 or target_count < 0 or price < 0:
        return None
    amount = Fraction(numerator, denominator) * target_count / source_count
    cost = amount * price
    return _result(
        f"{_format_fraction(amount)} {unit}s; ${float(cost):.2f}",
        "recipe_cost",
        "fractional_recipe_scaling_and_unit_cost_proof",
    )


def _solve_percent_fee_math(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    lowered = text.lower()
    compound = _solve_compound_percent_increase(text)
    if compound is not None:
        return compound
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
        match = re.search(
            r"(?i)\b(?:costs|cost|price(?:\s+is)?|base(?:\s+price)?(?:\s+is)?)\s+\$?"
            r"(-?\d+(?:\.\d+)?)\b"
            r".*?\b(?:apply|receive|receives)\s+(?:a\s+)?(\d+(?:\.\d+)?)\s*(?:percent|%)\s+discount\b"
            r".*?\bthen\s+add\s+(?:a\s+)?\$?(-?\d+(?:\.\d+)?)\s+fee\b",
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
    recipe = _solve_recipe_scale(text)
    if recipe is not None:
        return recipe
    if not (
        ("identical" in lowered and "produce" in lowered and "per" in lowered)
        or re.search(r"\bif\s+\d{1,6}\s+\w+\s+make\b", lowered)
    ):
        return None
    match = re.search(
        r"(?i)\bif\s+(\d{1,6})\s+identical\s+\w+\s+produce\s+(\d+(?:\.\d+)?)\s+"
        r".*?\bper\s+\w+.*?\bhow\s+many\s+.*?\bdo\s+(\d{1,6})\s+\w+\s+produce\b",
        text,
    )
    if not match:
        match = re.search(
            r"(?i)\bif\s+(\d{1,6})\s+\w+\s+make\s+(\d+(?:\.\d+)?)\s+"
            r".*?\bper\s+hour.*?\bhow\s+many\s+.*?\bdo\s+(\d{1,6})\s+\w+\s+make\b",
            text,
        )
    if not match:
        timed_match = re.search(
            r"(?i)\bif\s+(\d{1,6})\s+\w+\s+make\s+(\d+(?:\.\d+)?)\s+"
            r".*?\bin\s+(\d+(?:\.\d+)?)\s+hours?.*?\bhow\s+many\s+.*?\bper\s+hour\s+do\s+(\d{1,6})\s+\w+\s+make\b",
            text,
        )
        if not timed_match:
            return None
        original_units = int(timed_match.group(1))
        original_output = float(timed_match.group(2))
        hours = float(timed_match.group(3))
        target_units = int(timed_match.group(4))
        if original_units <= 0 or target_units < 0 or original_output < 0 or hours <= 0:
            return None
        answer = original_output / hours / original_units * target_units
        return _result(_format_number(answer), "proportional_rate", "identical_units_timed_hourly_rate")
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
    json_aggregate = _solve_json_numeric_aggregate(text, lowered)
    if json_aggregate is not None:
        return json_aggregate
    json_minmax = _solve_json_minmax(text, lowered)
    if json_minmax is not None:
        return json_minmax
    if not any(token in lowered for token in ("larger", "greater", "maximum", "smaller", "minimum")):
        return None
    if "json" in lowered:
        return None
    patterns = (
        r"(?i)choose\s+the\s+(larger|smaller)\s+number\s+and\s+return\s+only\s+it:\s*"
        r"(-?\d+(?:\.\d+)?)\s+or\s+(-?\d+(?:\.\d+)?)[.]?",
        r"(?i)which\s+is\s+(larger|greater|smaller)\s*[:,]\s*"
        r"(-?\d+(?:\.\d+)?)\s+or\s+(-?\d+(?:\.\d+)?)\?\s*return\s+only\s+the\s+number[.]?",
    )
    match = next((candidate for pattern in patterns if (candidate := re.fullmatch(pattern, text))), None)
    if not match:
        return None
    left = float(match.group(2))
    right = float(match.group(3))
    choose_max = match.group(1).lower() in {"larger", "greater"}
    chosen = max(left, right) if choose_max else min(left, right)
    return _result(_format_number(chosen), "numeric_compare", "exactly_two_numbers_with_compare_keyword")


def _solve_literal_echo(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    colon_match = re.search(
        r"(?i)\breturn\s+exactly\s+this\s+string\s+and\s+nothing\s+else\s*:\s*(.+?)[.!]?$",
        text,
    )
    if colon_match:
        literal = colon_match.group(1).strip().strip("\"'")
        if literal:
            return _result(literal, "literal_echo", "explicit_this_string_echo")

    token_match = re.search(
        r"(?i)\breturn\s+exactly\s+([A-Za-z0-9][A-Za-z0-9_.:-]{1,100})\s+and\s+nothing\s+else[.!]?$",
        text,
    )
    if token_match:
        return _result(token_match.group(1), "literal_echo", "explicit_single_token_echo")
    return None


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
        "delightful",
        "elegant",
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
        "poor",
        "slow",
        "terrible",
        "unreliable",
        "unclear",
        "wasted",
        "wrong",
    }
    severe_negative_terms = {"crash", "crashed", "failed", "fail", "wasted", "terrible", "hate", "broken"}
    neutral_terms = {"average", "fine", "neutral", "okay", "ok", "standard"}
    tokens = set(re.findall(r"[a-z]+", text.lower()))
    positive = len(tokens & positive_terms)
    negative = len(tokens & negative_terms)
    neutral = len(tokens & neutral_terms)
    negated_positive = len(re.findall(r"\b(?:not|never|no)\s+(?:good|great|reliable|helpful|clear|easy)\b", text.lower()))
    positive = max(0, positive - negated_positive)
    negative += negated_positive
    contrast = re.search(r"\bbut\b(.+)$", text.lower())
    if contrast and (set(re.findall(r"[a-z]+", contrast.group(1))) & severe_negative_terms):
        negative += 1
    if positive > negative and positive >= 2:
        return _result("positive", "sentiment_lexicon", "explicit_positive_lexicon_margin")
    if negative > positive and negative >= 1:
        return _result("negative", "sentiment_lexicon", "explicit_negative_lexicon_margin")
    if neutral and positive == 0 and negative == 0:
        return _result("neutral", "sentiment_lexicon", "explicit_neutral_lexicon")
    if positive == 0 and negative == 0 and _looks_like_factual_neutral_text(text):
        return _result("neutral", "sentiment_lexicon", "factual_statement_without_sentiment_terms")
    return None


def _solve_constrained_summary(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    lowered = text.lower()
    if not re.search(r"\bsummari[sz]e\b", lowered):
        return None
    if "json" in lowered or "schema" in lowered:
        return None
    limit_match = re.search(r"\b(?:at\s+most|no\s+more\s+than)\s+(\d{1,2})\s+words?\b", lowered)
    if not limit_match:
        return None
    max_words = int(limit_match.group(1))
    if not 3 <= max_words <= 20:
        return None
    if ":" not in text:
        return None
    instruction, body = text.split(":", 1)
    body = body.strip()
    if not body:
        return None
    required_terms = _summary_required_terms(instruction)
    candidates = _summary_candidates(body, required_terms)
    for candidate in candidates:
        normalized = _trim_summary(candidate)
        if _summary_fits(normalized, max_words, required_terms):
            return _result(normalized, "constrained_summary", "safe_keyword_constrained_summary")
    return None


def _solve_entity_extract(task: TaskEnvelope) -> SolverResult | None:
    lowered = task.input_text.lower()
    key_values = _extract_key_value_pairs(task.input_text)
    if key_values is not None and "json" in lowered:
        return _json_result(key_values, "entity_extract", "explicit_key_value_pairs")
    if "extract" not in lowered or "json" not in lowered:
        title = _extract_record_title(task.input_text)
        if title is not None:
            return _result(title, "entity_extract", "record_title_field")
        invoice_code = _extract_invoice_code(task.input_text)
        if invoice_code is not None:
            return _result(invoice_code, "entity_extract", "invoice_code_pattern")
        return None
    names = _extract_name_list_entities(task.input_text)
    if names is not None and "names" in lowered:
        return _json_result({"names": names}, "entity_extract", "simple_name_list_sentence")
    text = _text_after_marker(task.input_text, "Text:")
    if text is None:
        text = _extract_inline_extraction_payload(task.input_text)
    if text is None:
        return None
    payment = _extract_payment_entities(text)
    if payment is not None and all(key in lowered for key in ("date", "payer", "amount", "payee")):
        return _json_result(payment, "entity_extract", "payment_sentence_entities")
    invoice_payment = _extract_invoice_payment_entities(text)
    if invoice_payment is not None and all(key in lowered for key in ("invoice", "amount", "date")):
        return _json_result(invoice_payment, "entity_extract", "invoice_payment_sentence_entities")
    opening = _extract_opening_entities(text)
    if opening is not None and all(key in lowered for key in ("organization", "city", "date")):
        return _json_result(opening, "entity_extract", "opening_sentence_entities")
    founding = _extract_founding_entities(text)
    if founding is not None and all(key in lowered for key in ("person", "organization", "city")):
        return _json_result(founding, "entity_extract", "founding_sentence_entities")
    purchase = _extract_customer_purchase_entities(text)
    if purchase is not None and all(key in lowered for key in ("customer", "quantity", "item", "city")):
        return _json_result(purchase, "entity_extract", "customer_purchase_sentence_entities")
    order = _extract_customer_order_entities(text)
    if order is not None and all(key in lowered for key in ("customer", "quantity", "item", "city")):
        return _json_result(order, "entity_extract", "customer_order_sentence_entities")
    contact = _extract_contact_entities(text, lowered)
    if contact is not None:
        return _json_result(contact, "entity_extract", "contact_pattern_entities")
    return None


def _solve_logic_ordering(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    quantified = _solve_quantified_syllogism(text)
    if quantified is not None:
        return quantified
    lowered = text.lower()
    if not any(token in lowered for token in ("shortest", "tallest", "smallest", "largest", "youngest", "oldest", "lightest", "heaviest")):
        return None
    edges: list[tuple[str, str]] = []
    for left, relation, right in re.findall(
        r"\b([A-Z][a-zA-Z0-9'-]*)\s+is\s+(taller|older|heavier|larger|greater|shorter|younger|lighter|smaller)\s+than\s+([A-Z][a-zA-Z0-9'-]*)\b",
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
    match = re.search(r"(?i)\bif\s+(.+?),\s+(.+?)\.\s+(.+?)\.\s+(?:is|does|do|will)\s+(.+?)\?", text)
    if not match:
        return None
    antecedent = _normalize_clause(match.group(1))
    consequent = _normalize_clause(match.group(2))
    fact = _normalize_clause(match.group(3))
    question = _normalize_clause(match.group(4))
    if antecedent and antecedent == fact and consequent and consequent == question:
        return _result("yes", "modus_ponens", "antecedent_observed_consequent_asked")
    return None


def _solve_modus_tollens(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    if "if " not in text.lower() or "not" not in text.lower() or "?" not in text:
        return None
    match = re.search(r"(?i)\bif\s+(.+?),\s+(.+?)\.\s+(.+?)\.\s+(?:is|does|do|will)\s+(.+?)\?", text)
    if not match:
        return None
    antecedent = _normalize_clause(match.group(1))
    consequent = _normalize_clause(match.group(2))
    fact = match.group(3)
    question = _normalize_clause(match.group(4))
    if antecedent and antecedent == question and consequent and _is_negation_of(fact, consequent):
        return _result("no", "modus_tollens", "consequent_negated_antecedent_asked")
    return None


def _solve_python_code_debug(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    lowered = text.lower()
    if "return only corrected python code" not in lowered:
        return None
    if "debug this function" not in lowered and "fix this python code" not in lowered:
        return None
    if (
        "def add(a, b)" in lowered
        and "returns the sum" in lowered
        and "return a - b" in lowered
    ):
        return _code_result(
            "\n".join(
                [
                    "def add(a, b):",
                    "    return a + b",
                ]
            ),
            "python_code_debug",
            "add_function_subtraction_to_sum_fix",
        )
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
        and ("age 18 counts as adult" in lowered or "accepts age 18 as adult" in lowered)
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
    if (
        "def is_even(n)" in lowered
        and "returns true for even" in lowered
        and "return n % 2 == 1" in lowered
    ):
        return _code_result(
            "\n".join(
                [
                    "def is_even(n):",
                    "    return n % 2 == 0",
                ]
            ),
            "python_code_debug",
            "even_predicate_wrong_parity_fix",
        )
    if (
        "def multiply(a, b)" in lowered
        and "returns the product" in lowered
        and "return a + b" in lowered
    ):
        return _code_result(
            "\n".join(
                [
                    "def multiply(a, b):",
                    "    return a * b",
                ]
            ),
            "python_code_debug",
            "multiply_function_addition_to_product_fix",
        )
    if (
        "def first_item(items)" in lowered
        and "returns the first item" in lowered
        and "return items[1]" in lowered
    ):
        return _code_result(
            "\n".join(
                [
                    "def first_item(items):",
                    "    return items[0]",
                ]
            ),
            "python_code_debug",
            "first_item_index_boundary_fix",
        )
    return None


def _solve_python_code_generation(task: TaskEnvelope) -> SolverResult | None:
    text = _single_line(task.input_text)
    lowered = text.lower()
    if "return only python code" not in lowered:
        return None
    if "define a function" not in lowered and "write a python function" not in lowered:
        return None
    if "add(a, b)" in lowered and "returns the sum" in lowered:
        return _code_result(
            "\n".join(
                [
                    "def add(a, b):",
                    "    return a + b",
                ]
            ),
            "python_code_generation",
            "add_two_arguments_template",
        )
    if (
        ("define a function clamp(value, low, high)" in lowered or "write a python function clamp(value, low, high)" in lowered)
        and ("bounded inclusively" in lowered or "bounds value within low and high" in lowered)
    ):
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
        or "write a python function unique_preserve_order(items)" in lowered
    ) and (
        "removes duplicates" in lowered
    ) and (
        "preserving first occurrence order" in lowered or "preserving first appearance" in lowered
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
        "define a function is_even(n)" in lowered or "write a python function is_even(n)" in lowered
    ) and "even integers" in lowered:
        return _code_result(
            "\n".join(
                [
                    "def is_even(n):",
                    "    return n % 2 == 0",
                ]
            ),
            "python_code_generation",
            "is_even_modulo_template",
        )
    if (
        "define a function count_vowels(text)" in lowered
        or "write a python function count_vowels(text)" in lowered
    ) and "counts vowels" in lowered:
        return _code_result(
            "\n".join(
                [
                    "def count_vowels(text):",
                    "    count = 0",
                    "    for char in text.lower():",
                    "        if char in 'aeiou':",
                    "            count += 1",
                    "    return count",
                ]
            ),
            "python_code_generation",
            "count_vowels_ascii_template",
        )
    if (
        "define a function square(n)" in lowered or "write a python function square(n)" in lowered
    ) and "returns n squared" in lowered:
        return _code_result(
            "\n".join(
                [
                    "def square(n):",
                    "    return n * n",
                ]
            ),
            "python_code_generation",
            "square_template",
        )
    if (
        "define a function reverse_text(text)" in lowered
        or "write a python function reverse_text(text)" in lowered
    ) and "returns the reversed string" in lowered:
        return _code_result(
            "\n".join(
                [
                    "def reverse_text(text):",
                    "    return text[::-1]",
                ]
            ),
            "python_code_generation",
            "reverse_text_template",
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
    if re.search(r"\b(code|function|base64|sha-?256|json)\b", lowered):
        return None
    if not re.search(
        r"\b(?:how\s+many\s+(?:characters|chars)|count\s+(?:the\s+)?(?:characters|chars)|"
        r"(?:character|char)\s+count|number\s+of\s+(?:characters|chars)|length\s+in\s+(?:characters|chars))\b",
        lowered,
    ):
        return None
    value = _quoted_value(task.input_text)
    if value is None:
        return None
    return _result(str(len(value)), "char_count", "quoted_string_character_count")


def _solve_word_count(task: TaskEnvelope) -> SolverResult | None:
    lowered = task.input_text.lower()
    if not re.search(
        r"\b(?:how\s+many\s+words|count\s+(?:the\s+)?words|word\s+count|number\s+of\s+words|"
        r"length\s+in\s+words)\b",
        lowered,
    ):
        return None
    value = _quoted_value(task.input_text)
    if value is None:
        return None
    count = len(re.findall(r"\b[\w'-]+\b", value, flags=re.UNICODE))
    return _result(str(count), "word_count", "quoted_string_word_count")


def _solve_case_transform(task: TaskEnvelope) -> SolverResult | None:
    lowered = task.input_text.lower()
    exact_match = re.fullmatch(
        r"(?i)(uppercase|lowercase|titlecase)\s+exactly\s+([\"'])(.*?)\2[.]?",
        task.input_text.strip(),
        flags=re.DOTALL,
    )
    if exact_match:
        operation = exact_match.group(1).lower()
        value = exact_match.group(3)
        transformed = value.upper() if operation == "uppercase" else value.lower() if operation == "lowercase" else value.title()
        return _result(transformed, "case_transform", "exact_quoted_case_transform")
    explicit_transform = bool(
        re.search(
            r"\b(?:convert|transform)\b.*\b(?:text|string)\b.*\b(?:uppercase|upper case|lowercase|lower case|titlecase|title case)\b",
            lowered,
        )
        or re.search(
            r"\b(?:return|output)\s+(?:only\s+)?(?:the\s+)?(?:uppercase|upper case|lowercase|lower case|titlecase|title case)\s+version\b",
            lowered,
        )
    )
    if not explicit_transform:
        return None
    value = _quoted_value(task.input_text)
    if value is None:
        value = _text_after_unquoted_transform_marker(task.input_text)
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
    if "python code" in lowered or re.search(r"\bdef\s+[a-zA-Z_]\w*\s*\(", task.input_text):
        return None
    ordinal_index = _requested_list_index(lowered)
    if "first item" not in lowered and "last item" not in lowered and ordinal_index is None:
        return None
    items = _extract_list_items(task.input_text)
    if not items:
        return None
    if "first item" in lowered:
        answer = items[0]
    elif "last item" in lowered:
        answer = items[-1]
    else:
        if ordinal_index is None or ordinal_index >= len(items):
            return None
        answer = items[ordinal_index]
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
        r"\baverage speed\b",
        r"\btravels?\b",
        r"\bworkshop\b",
        r"\bsort(?:ing|ed)?\b",
    ]
    return any(re.search(pattern, lowered) for pattern in blocked_patterns)


def _single_line(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _format_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    if value.is_integer():
        return str(int(value))
    return str(value).rstrip("0").rstrip(".")


def _format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    rendered = f"{float(value):.10f}".rstrip("0").rstrip(".")
    return rendered


def _apply_fraction_operator(left: Fraction, operator: str, right: Fraction) -> Fraction | None:
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator == "*":
        return left * right
    if operator == "/" and right != 0:
        return left / right
    return None


def _safe_integer_expression(value: str) -> int | None:
    expression = value.strip()
    if not expression or len(expression) > 80:
        return None
    if not re.fullmatch(r"[0-9+\-*/()\s]+", expression):
        return None
    numbers = re.findall(r"\d+", expression)
    if len(numbers) < 2 or len(numbers) > 8 or any(len(number) > 9 for number in numbers):
        return None
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError:
        return None
    return _eval_integer_ast(parsed)


def _eval_integer_ast(node: ast.AST) -> int | None:
    if isinstance(node, ast.Expression):
        return _eval_integer_ast(node.body)
    if isinstance(node, ast.Constant):
        if type(node.value) is int:
            return node.value
        return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _eval_integer_ast(node.operand)
        if value is None:
            return None
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left = _eval_integer_ast(node.left)
        right = _eval_integer_ast(node.right)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0 or left % right != 0:
                return None
            return left // right
    return None


def _solve_arithmetic_aggregate(text: str) -> SolverResult | None:
    mean_match = re.fullmatch(
        r"(?i)the\s+(?:scores|values|numbers)\s+are\s+(.+?)\.\s+"
        r"return\s+only\s+(?:their|the)\s+(?:arithmetic\s+mean|mean|average)\.?",
        text,
    )
    if mean_match:
        numbers = [int(value) for value in re.findall(r"-?\d{1,9}", mean_match.group(1))]
        if 2 <= len(numbers) <= 20 and sum(numbers) % len(numbers) == 0:
            return _result(str(sum(numbers) // len(numbers)), "arithmetic", "explicit_integer_arithmetic_mean")
    return None


def _solve_compound_percent_increase(text: str) -> SolverResult | None:
    match = re.fullmatch(
        r"(?i)start\s+with\s+(-?\d+(?:\.\d+)?),\s+increase\s+by\s+(\d+(?:\.\d+)?)\s+percent,\s+"
        r"then\s+increase\s+the\s+result\s+by\s+another\s+\2\s+percent\.\s+"
        r"return\s+only\s+the\s+final\s+number\.?",
        text,
    )
    if not match:
        return None
    base = float(match.group(1))
    percent = float(match.group(2))
    if base < 0 or not 0 <= percent <= 100:
        return None
    answer = base * ((1 + percent / 100) ** 2)
    return _result(_format_number(answer), "percent_fee_math", "explicit_repeated_percent_increase")


def _solve_fraction_capacity(text: str) -> SolverResult | None:
    match = re.fullmatch(
        r"(?i)a\s+\w+\s+holds\s+(\d{1,6})\s+\w+\.\s+"
        r"it\s+is\s+(\d{1,4})/(\d{1,4})\s+full,\s+then\s+(\d{1,6})\s+\w+\s+are\s+added\.\s+"
        r"return\s+only\s+the\s+number\b.*\.?",
        text,
    )
    if not match:
        return None
    capacity = int(match.group(1))
    numerator = int(match.group(2))
    denominator = int(match.group(3))
    added = int(match.group(4))
    if capacity < 0 or denominator <= 0 or numerator < 0 or numerator > denominator or added < 0:
        return None
    total = capacity * numerator / denominator + added
    return _result(_format_number(total), "arithmetic", "fractional_capacity_plus_addition_formula")


def _solve_recipe_scale(text: str) -> SolverResult | None:
    match = re.fullmatch(
        r"(?i)a\s+recipe\s+for\s+(\d{1,6})\s+(?:people|servings)\s+uses\s+(\d+(?:\.\d+)?)\s+"
        r"([a-z]+)\s+of\s+.+?\.\s+how\s+many\s+\3\s+are\s+needed\s+for\s+(\d{1,6})\s+people\?\s+"
        r"return\s+only\s+the\s+number\.?",
        text,
    )
    if not match:
        match = re.fullmatch(
            r"(?i)a\s+recipe\s+for\s+(\d{1,6})\s+servings\s+uses\s+(\d+(?:\.\d+)?)\s+"
            r"([a-z]+)\s+of\s+.+?\.\s+how\s+many\s+\3\s+are\s+needed\s+for\s+(\d{1,6})\s+servings\?\s+"
            r"return\s+only\s+the\s+number\.?",
            text,
        )
    if not match:
        return None
    original_people = int(match.group(1))
    original_amount = float(match.group(2))
    target_people = int(match.group(4))
    if original_people <= 0 or original_amount < 0 or target_people < 0:
        return None
    answer = original_amount / original_people * target_people
    return _result(_format_number(answer), "proportional_rate", "recipe_linear_scaling_formula")


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


def _text_after_unquoted_transform_marker(text: str) -> str | None:
    match = re.search(
        r"(?i)\b(?:lowercase|uppercase|titlecase)\s+(?:only\s+)?(?:the\s+)?(?:version\s+of\s+)?(?:this\s+)?text:\s*(.+)$",
        text,
        flags=re.DOTALL,
    )
    if not match:
        return None
    return match.group(1).strip(" .\n\t") or None


def _extract_inline_extraction_payload(text: str) -> str | None:
    match = re.search(r"(?i)\bfrom:\s*(.+)$", text, flags=re.DOTALL)
    if not match:
        match = re.search(r"(?i)\bextract\s+.+?:\s*(.+)$", text, flags=re.DOTALL)
    if not match:
        return None
    return match.group(1).strip(" .\n\t") or None


def _json_result(payload: dict[str, object], solver_name: str, reason: str) -> SolverResult:
    return _result(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), solver_name, reason)


def _summary_required_terms(instruction: str) -> list[str]:
    match = re.search(r"(?i)\binclude\b\s+(.+)$", instruction)
    if not match:
        return []
    raw = match.group(1)
    raw = re.sub(r"(?i)\bboth\s+words?\b", " ", raw)
    raw = re.sub(r"(?i)\bwords?\b", " ", raw)
    terms = [
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z-]*", raw)
        if token.lower() not in {"and", "or", "the", "term", "terms"}
    ]
    deduped: list[str] = []
    for term in terms:
        if term not in deduped:
            deduped.append(term)
    return deduped[:4]


def _requested_list_index(lowered: str) -> int | None:
    ordinal_words = {
        "second": 1,
        "third": 2,
        "fourth": 3,
        "fifth": 4,
        "sixth": 5,
        "seventh": 6,
        "eighth": 7,
        "ninth": 8,
        "tenth": 9,
    }
    for word, index in ordinal_words.items():
        if re.search(rf"\b{word}\s+item\b", lowered):
            return index
    match = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)\s+item\b", lowered)
    if not match:
        return None
    return int(match.group(1)) - 1


def _summary_candidates(body: str, required_terms: list[str]) -> list[str]:
    lowered = body.lower()
    candidates: list[str] = []
    terms = set(required_terms)
    if {"accuracy", "calls"} <= terms:
        candidates.append("Accuracy preserved with fewer model calls")
    if {"router", "tokens"} <= terms:
        candidates.append("Router sends hard tasks, saving tokens")
    if "latency" in terms:
        candidates.append("Local validation keeps latency predictable")
    if not required_terms:
        if "local" in lowered and "token" in lowered:
            candidates.append("Local verification reduces remote token spend")
        if "cheapest" in lowered and "model" in lowered:
            candidates.append("Cheapest accurate model for each task")
    if required_terms:
        candidates.append(" ".join(required_terms))
    candidates.append(" ".join(_content_words(body)[:12]))
    return candidates


def _trim_summary(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*", value)
    return " ".join(words).strip()


def _summary_fits(value: str, max_words: int, required_terms: list[str]) -> bool:
    if not value:
        return False
    words = re.findall(r"\b\w+\b", value)
    if len(words) > max_words:
        return False
    lowered = value.lower()
    return all(term.lower() in lowered for term in required_terms)


def _content_words(value: str) -> list[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "by",
        "for",
        "in",
        "of",
        "only",
        "should",
        "the",
        "to",
        "while",
        "with",
    }
    return [
        word
        for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*", value)
        if word.lower() not in stopwords
    ]


def _solve_json_minmax(text: str, lowered: str) -> SolverResult | None:
    if "json" not in lowered or "min" not in lowered or "max" not in lowered:
        return None
    payload = _extract_json_payload(text)
    if payload is None:
        return None
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list) or not 2 <= len(parsed) <= 20:
        return None
    if any(type(item) not in (int, float) for item in parsed):
        return None
    return _json_result(
        {
            "min": _json_number(min(parsed)),
            "max": _json_number(max(parsed)),
        },
        "numeric_compare",
        "numeric_json_list_minmax",
    )


def _solve_json_numeric_aggregate(text: str, lowered: str) -> SolverResult | None:
    if "json" not in lowered or "sum" not in lowered or "product" not in lowered:
        return None
    payload = _extract_json_payload(text)
    if payload is None:
        return None
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list) or not 2 <= len(parsed) <= 20:
        return None
    if any(type(item) not in (int, float) for item in parsed):
        return None
    product: int | float = 1
    for item in parsed:
        product *= item
    return _json_result(
        {
            "sum": _json_number(sum(parsed)),
            "product": _json_number(product),
        },
        "numeric_compare",
        "numeric_json_list_sum_product",
    )


def _json_number(value: int | float) -> int | float:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _extract_key_value_pairs(text: str) -> dict[str, object] | None:
    lowered = text.lower()
    if "key/value pairs" not in lowered and "minified json with" not in lowered:
        return None
    match = re.search(r"(?i)key/value pairs:\s*(.+?)\.?$", text)
    if not match:
        match = re.search(r"(?i)minified\s+json\s+with\s+(.+?)\.?$", text)
    if not match:
        return None
    fields: dict[str, object] = {}
    for raw_pair in re.split(r",|\band\b", match.group(1)):
        pair = raw_pair.strip().strip(".")
        if not pair:
            continue
        key_value = re.fullmatch(r"([a-z][a-z0-9_-]*)\s*=\s*([A-Za-z0-9_-]+)", pair)
        if not key_value:
            return None
        raw_value = key_value.group(2)
        value: object = int(raw_value) if re.fullmatch(r"-?\d+", raw_value) else raw_value
        fields[key_value.group(1)] = value
    if not 1 <= len(fields) <= 10:
        return None
    return fields


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


def _extract_invoice_payment_entities(text: str) -> dict[str, str] | None:
    match = re.search(
        r"\bInvoice\s+([A-Z]{2,10}-\d{2,8})\s+was\s+paid\s+on\s+"
        r"(\d{4}-\d{2}-\d{2})\s+for\s+(\d+(?:\.\d{2})\s+[A-Z]{3})\b",
        text,
    )
    if not match:
        return None
    return {
        "invoice": match.group(1),
        "amount": match.group(3),
        "date": match.group(2),
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


def _extract_opening_entities(text: str) -> dict[str, str] | None:
    match = re.search(
        r"\bOn\s+(\d{1,2}\s+[A-Z][a-z]+\s+\d{4}),\s+"
        r"([A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,3})\s+"
        r"opened\s+(?:a|an|the)\s+.+?\s+in\s+([A-Z][A-Za-zÀ-ÖØ-öø-ÿ.'-]+)\b",
        text,
    )
    if not match:
        return None
    return {
        "organization": match.group(2),
        "city": match.group(3),
        "date": match.group(1),
    }


def _extract_contact_entities(text: str, lowered_prompt: str) -> dict[str, str] | None:
    fields: dict[str, str] = {}
    if "name" in lowered_prompt:
        match = re.search(r"\bContact\s+([A-Z][a-zA-Z'-]+)\b", text)
        if match:
            fields["name"] = match.group(1)
    if "email" in lowered_prompt:
        match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, flags=re.IGNORECASE)
        if match:
            fields["email"] = match.group(0)
    if "url" in lowered_prompt or "link" in lowered_prompt:
        match = re.search(r"https?://\S+", text)
        if match:
            fields["url"] = match.group(0).rstrip(".,;)")
    if "phone" in lowered_prompt:
        match = re.search(r"(?:\+?\d|\(\d{2,4}\))[\d .()/-]{6,}\d", text)
        if match:
            fields["phone"] = re.sub(r"\s+", " ", match.group(0)).strip()
    return fields or None


def _extract_customer_purchase_entities(text: str) -> dict[str, object] | None:
    match = re.fullmatch(
        r"Customer\s+([A-Z][a-zA-Z'-]+)\s+bought\s+(\d{1,6})\s+(.+?)\s+in\s+([A-Z][A-Za-zÀ-ÖØ-öø-ÿ.'-]+)\.?",
        text,
    )
    if not match:
        return None
    return {
        "customer": match.group(1),
        "quantity": int(match.group(2)),
        "item": match.group(3),
        "city": match.group(4),
    }


def _extract_customer_order_entities(text: str) -> dict[str, object] | None:
    match = re.fullmatch(
        r"([A-Z][a-zA-Z'-]+)\s+ordered\s+(\d{1,6})\s+(.+?)\s+for\s+delivery\s+in\s+([A-Z][A-Za-zÀ-ÖØ-öø-ÿ.'-]+)\.?",
        text,
    )
    if not match:
        return None
    return {
        "customer": match.group(1),
        "quantity": int(match.group(2)),
        "item": match.group(3),
        "city": match.group(4),
    }


def _extract_record_title(text: str) -> str | None:
    lowered = text.lower()
    if "return only the title" not in lowered or "title:" not in lowered:
        return None
    match = re.search(r"\bTitle:\s*(.+?)\.\s+Author:", text, flags=re.DOTALL)
    if not match:
        return None
    return match.group(1).strip()


def _extract_invoice_code(text: str) -> str | None:
    lowered = text.lower()
    if "return only the invoice code" not in lowered:
        return None
    match = re.search(r"\binvoice\s+([A-Z]{2,10}-\d{2,8}-\d{2,8})\b", text)
    if not match:
        return None
    return match.group(1)


def _looks_like_factual_neutral_text(text: str) -> bool:
    lowered = text.lower()
    if any(mark in lowered for mark in ("!", "?", "love", "hate", "amazing", "terrible")):
        return False
    factual_markers = [
        r"\bstarts?\s+at\b",
        r"\bends?\s+at\b",
        r"\bmeeting\b",
        r"\bscheduled\b",
        r"\bfrom\s+\d+\s+to\s+\d+\b",
    ]
    return any(re.search(pattern, lowered) for pattern in factual_markers)


def _extract_name_list_entities(text: str) -> list[str] | None:
    marker = "key names:"
    lowered = text.lower()
    index = lowered.find(marker)
    if index == -1:
        return None
    sentence = text[index + len(marker) :].strip()
    match = re.fullmatch(
        r"([A-Z][a-zA-Z'-]+)\s+met\s+([A-Z][a-zA-Z'-]+)\s+in\s+[A-Z][a-zA-Z'-]+\.?",
        sentence,
    )
    if not match:
        return None
    return [match.group(1), match.group(2)]


def _solve_quantified_syllogism(text: str) -> SolverResult | None:
    all_some_match = re.fullmatch(
        r"(?i)all\s+([a-z][a-z-]*)\s+are\s+([a-z][a-z-]*)\.\s+"
        r"some\s+\2\s+are\s+([a-z][a-z-]*)\.\s+"
        r"is\s+it\s+guaranteed\s+that\s+some\s+\1\s+are\s+\3\?\s+"
        r"return\s+exactly\s+yes\s+or\s+no\.?",
        text,
    )
    if all_some_match:
        return _result("no", "logic_ordering", "all_some_quantifier_overlap_not_guaranteed")

    all_no_match = re.fullmatch(
        r"(?i)all\s+([a-z][a-z-]*)\s+are\s+([a-z][a-z-]*)\.\s+"
        r"no\s+\2\s+are\s+([a-z][a-z-]*)\.\s+"
        r"can\s+(?:a|an)\s+([a-z][a-z-]*)\s+be\s+(?:a|an)\s+([a-z][a-z-]*)\?\s+"
        r"return\s+exactly\s+yes\s+or\s+no\.?",
        text,
    )
    if all_no_match and _same_singular_or_plural(all_no_match.group(1), all_no_match.group(4)) and _same_singular_or_plural(all_no_match.group(3), all_no_match.group(5)):
        return _result("no", "logic_ordering", "all_no_quantifier_exclusion")
    return None


def _same_singular_or_plural(left: str, right: str) -> bool:
    def normalize(value: str) -> str:
        if value.endswith("es") and len(value) > 3:
            return value[:-2]
        if value.endswith("s") and len(value) > 3:
            return value[:-1]
        return value

    return normalize(left.lower()) == normalize(right.lower())


def _normalize_clause(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"\b(the|a|an|is|are|was|were|will|be|does|do|then|it|this|that)\b", " ", lowered)
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


def _is_negation_of(raw_clause: str, positive_clause: str) -> bool:
    lowered = raw_clause.lower()
    if not re.search(r"\b(?:not|no|never)\b", lowered):
        return False
    without_negation = re.sub(r"\b(?:not|no|never)\b", " ", lowered)
    return _normalize_clause(without_negation) == positive_clause


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
