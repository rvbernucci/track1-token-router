from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from router.core.contracts import FeatureVector, RequestedOutputShape
from router.orchestration.assessment import approximate_token_count, detect_requested_output_shape


E2B_MECHANICAL_FEATURE_SCHEMA_VERSION = "e2b-mechanical-features-v2"
MAX_PROMPT_CHARS = 32_768
MAX_SOURCE_CHARS = 24_000

_CODE_FENCE = re.compile(r"```(?:python|javascript|typescript|js|ts|java|go|rust|cpp|c\+\+)?\s*\n(.*?)```", re.I | re.S)
_CODE_LINE = re.compile(r"(?m)^\s*(?:def |class |function |const |let |var |if\s*\(|for\s*\(|while\s*\(|return\b|import\b|from\b)")
_CURRENTNESS = re.compile(r"\b(?:today|currently|latest|now|this (?:week|month|year)|current|real[- ]time|recent)\b", re.I)
_EXTERNAL = re.compile(r"\b(?:look up|search|browse|website|internet|online|according to|cite sources?|url|https?://)\b", re.I)
_NEGATION = re.compile(r"\b(?:not|never|except|neither|without|unless|no\b|não|nunca|sin)\b", re.I)
_AMBIGUITY = re.compile(r"\b(?:maybe|possibly|could mean|ambiguous|unclear|it depends|approximately|roughly)\b", re.I)
_INJECTION = re.compile(r"\b(?:ignore (?:all |any )?(?:previous|prior|above)|system prompt|developer message|jailbreak|override instructions)\b", re.I)
_STRICT_FORMAT = re.compile(r"\b(?:return|respond|output|answer|write)\s+(?:with\s+)?(?:only|exactly|in valid|as (?:a|an))\b", re.I)
_JSON = re.compile(r"\b(?:json|jsonl|json schema)\b", re.I)
_CLOSED_LABEL = re.compile(r"\b(?:one of|choose from|positive|negative|neutral|true or false|yes or no)\b", re.I)
_SENTENCE_LIMIT = re.compile(
    r"\b(?:in|using|maximum|at most|exactly|em|usando|máximo|no máximo|exatamente|en|como máximo|exactamente)"
    r"\s+(\d+)\s+(?:sentences?|frases?|oraciones?)\b",
    re.I,
)
_WORD_LIMIT = re.compile(
    r"\b(?:in|using|maximum|at most|exactly|under|em|usando|máximo|no máximo|exatamente|menos de|en|como máximo|exactamente)"
    r"\s+(\d+)\s+(?:words?|palavras?|palabras?)\b",
    re.I,
)
_ENTITY_TYPES = re.compile(r"\b(?:person|people|organization|organisation|company|location|place|date|money|product|event|entity|entities)\b", re.I)
_MATH_OPERATOR = re.compile(r"(?:\+|(?<!\w)-(?!\w)|\*|/|=|%|\^|×|÷|≤|≥|<|>)")
_VARIABLE = re.compile(r"\b[a-zA-Z]\b")


@dataclass(frozen=True)
class E2BMechanicalFeatures:
    values: tuple[tuple[str, float], ...]
    schema_version: str = E2B_MECHANICAL_FEATURE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        names = [name for name, _ in self.values]
        if self.schema_version != E2B_MECHANICAL_FEATURE_SCHEMA_VERSION:
            raise ValueError("Unsupported E2B mechanical feature schema.")
        if not names or len(names) != len(set(names)):
            raise ValueError("E2B mechanical feature names must be non-empty and unique.")
        if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for _, value in self.values):
            raise ValueError("E2B mechanical feature values must be finite values in [0, 1].")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "features": {name: value for name, value in self.values},
        }

    def to_vector(self) -> FeatureVector:
        return FeatureVector(
            names=tuple(name for name, _ in self.values),
            values=tuple(value for _, value in self.values),
        )


def extract_e2b_mechanical_features(prompt: str) -> E2BMechanicalFeatures:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Prompt must be a non-empty string.")
    shape = detect_requested_output_shape(prompt)
    tokens = approximate_token_count(prompt)
    words = re.findall(r"\b\w+\b", prompt, flags=re.UNICODE)
    numbers = re.findall(r"(?<!\w)[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?!\w)", prompt)
    code_blocks = _CODE_FENCE.findall(prompt)
    code_text = "\n".join(code_blocks) if code_blocks else "\n".join(_CODE_LINE.findall(prompt))
    source_chars = _source_text_chars(prompt)
    sentence_limit = _first_bounded(_SENTENCE_LIMIT, prompt, ceiling=20)
    word_limit = _first_bounded(_WORD_LIMIT, prompt, ceiling=500)
    language = _language(prompt)
    values: list[tuple[str, float]] = [
        ("mechanical.prompt_chars_log", _log_ratio(len(prompt), MAX_PROMPT_CHARS)),
        ("mechanical.prompt_tokens_log", _log_ratio(tokens, 8192)),
        ("mechanical.word_count_log", _log_ratio(len(words), 8192)),
        ("mechanical.source_chars_log", _log_ratio(source_chars, MAX_SOURCE_CHARS)),
        ("mechanical.number_density", min(1.0, len(numbers) / max(1, len(words)) * 8.0)),
        ("mechanical.operator_count", min(1.0, len(_MATH_OPERATOR.findall(prompt)) / 12.0)),
        ("mechanical.variable_count", min(1.0, len(_VARIABLE.findall(prompt)) / 12.0)),
        ("mechanical.entity_type_count", min(1.0, len(set(x.casefold() for x in _ENTITY_TYPES.findall(prompt))) / 6.0)),
        ("mechanical.code_present", float(bool(code_blocks or _CODE_LINE.search(prompt)))),
        ("mechanical.code_lines_log", _log_ratio(len(code_text.splitlines()) if code_text else 0, 256)),
        ("mechanical.code_branch_count", min(1.0, len(re.findall(r"\b(?:if|elif|else|switch|case)\b", prompt)) / 10.0)),
        ("mechanical.code_loop_count", min(1.0, len(re.findall(r"\b(?:for|while)\b", prompt)) / 8.0)),
        ("mechanical.currentness", float(bool(_CURRENTNESS.search(prompt)))),
        ("mechanical.external_knowledge", float(bool(_EXTERNAL.search(prompt)))),
        ("mechanical.negation", float(bool(_NEGATION.search(prompt)))),
        ("mechanical.ambiguity", float(bool(_AMBIGUITY.search(prompt)))),
        ("mechanical.prompt_injection", float(bool(_INJECTION.search(prompt)))),
        ("mechanical.strict_format", float(bool(_STRICT_FORMAT.search(prompt)))),
        ("mechanical.json_requested", float(bool(_JSON.search(prompt)))),
        ("mechanical.sentence_limit", sentence_limit / 20.0),
        ("mechanical.word_limit", word_limit / 500.0),
        ("mechanical.verifier.numeric", float(shape is RequestedOutputShape.NUMBER)),
        ("mechanical.verifier.closed_label", float(shape is RequestedOutputShape.BOOLEAN or bool(_CLOSED_LABEL.search(prompt)))),
        ("mechanical.verifier.json_structure", float(shape is RequestedOutputShape.JSON)),
        ("mechanical.verifier.code_syntax", float(shape is RequestedOutputShape.CODE or bool(code_blocks or _CODE_LINE.search(prompt)))),
        ("mechanical.language_en", float(language == "en")),
        ("mechanical.language_pt", float(language == "pt")),
        ("mechanical.language_es", float(language == "es")),
        ("mechanical.language_other", float(language == "other")),
    ]
    for candidate in RequestedOutputShape:
        values.append((f"mechanical.shape.{candidate.value}", float(shape is candidate)))
    for language_name in ("python", "javascript", "typescript", "other"):
        values.append((f"mechanical.code_language.{language_name}", float(_code_language(prompt) == language_name)))
    return E2BMechanicalFeatures(tuple(values))


def _log_ratio(value: int, ceiling: int) -> float:
    return min(1.0, math.log1p(max(0, value)) / math.log1p(ceiling))


def _first_bounded(pattern: re.Pattern[str], text: str, *, ceiling: int) -> int:
    match = pattern.search(text)
    return min(ceiling, int(match.group(1))) if match else 0


def _source_text_chars(prompt: str) -> int:
    markers = tuple(marker for marker in ("text:", "passage:", "article:", "document:", "source:") if marker in prompt.casefold())
    if markers:
        positions = [prompt.casefold().find(marker) + len(marker) for marker in markers]
        return max(0, len(prompt) - min(positions))
    blocks = re.findall(r"(?:\n\s*){2,}(.+)", prompt, flags=re.S)
    return len(blocks[-1]) if blocks else 0


def _language(prompt: str) -> str:
    lowered = f" {prompt.casefold()} "
    scores = {
        "pt": sum(lowered.count(token) for token in (" não ", " para ", " uma ", " resposta ", " seguinte ", " somente ")),
        "es": sum(lowered.count(token) for token in (" para ", " una ", " respuesta ", " siguiente ", " solamente ", " cuál ")),
        "en": sum(lowered.count(token) for token in (" the ", " answer ", " return ", " following ", " only ", " what ")),
    }
    winner = max(scores, key=scores.get)
    return winner if scores[winner] > 0 else "other"


def _code_language(prompt: str) -> str:
    lowered = prompt.casefold()
    if "typescript" in lowered or re.search(r"\binterface\s+\w+", prompt):
        return "typescript"
    if "javascript" in lowered or re.search(r"\b(?:const|let|var)\s+\w+\s*=", prompt):
        return "javascript"
    if "python" in lowered or re.search(r"(?m)^\s*(?:def|class)\s+\w+.*:", prompt):
        return "python"
    return "other"
