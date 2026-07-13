from __future__ import annotations

import ast
import json
import re
import textwrap
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from router.core.contracts import AnswerResult, TaskEnvelope
from router.orchestration.prompt_packet import extract_literal_echo, infer_expected_format


@dataclass(frozen=True)
class FinalValidationResult:
    valid: bool
    expected_format: str
    reason: str
    repaired_answer: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


ANSWER_CONTRACT_SCHEMA_VERSION = "answer-contract-v2"


class AnswerContractKind(str, Enum):
    FREE_TEXT = "free_text"
    JSON = "json"
    NUMBER = "number"
    LITERAL_ECHO = "literal_echo"
    YES_NO = "yes_no"
    UPPERCASE = "uppercase"
    CODE = "code"
    LABEL = "label"


@dataclass(frozen=True)
class AnswerContract:
    kind: AnswerContractKind
    strict: bool
    allowed_values: tuple[str, ...] = ()
    json_keys: tuple[str, ...] = ()
    exact_words: int | None = None
    max_words: int | None = None
    exact_sentences: int | None = None
    max_sentences: int | None = None
    exact_items: int | None = None
    max_items: int | None = None
    schema_version: str = ANSWER_CONTRACT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = self.kind.value
        return payload


@dataclass(frozen=True)
class AnswerContractResult:
    valid: bool
    answer: str
    original_answer: str
    reason: str
    contract: AnswerContract
    actions: tuple[str, ...] = ()
    ambiguous: bool = False

    @property
    def changed(self) -> bool:
        return self.answer != self.original_answer.strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ANSWER_CONTRACT_SCHEMA_VERSION,
            "valid": self.valid,
            "reason": self.reason,
            "changed": self.changed,
            "actions": list(self.actions),
            "ambiguous": self.ambiguous,
            "contract": self.contract.to_dict(),
        }


def infer_answer_contract(task: TaskEnvelope) -> AnswerContract:
    prompt = task.input_text
    expected = infer_expected_format(task)
    kind = AnswerContractKind(expected)
    labels = _extract_allowed_labels(prompt)
    if kind is AnswerContractKind.FREE_TEXT and labels:
        kind = AnswerContractKind.LABEL
    return AnswerContract(
        kind=kind,
        strict=bool(
            re.search(
                r"\b(?:return|answer|respond)(?:\s+with)?\s+(?:only|exactly)\b|"
                r"\bno commentary\b|\bnothing else\b|"
                r"\bexactly\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
                r"(?:words?|sentences?|items?|bullet(?: points?)?)\b",
                prompt,
                re.IGNORECASE,
            )
        ),
        allowed_values=labels if kind is AnswerContractKind.LABEL else (),
        json_keys=_extract_json_keys(prompt) if kind is AnswerContractKind.JSON else (),
        exact_words=_constraint_integer(prompt, r"exactly\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+words?"),
        max_words=_constraint_integer(prompt, r"(?:at most|no more than|maximum(?: of)?)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+words?"),
        exact_sentences=_exact_sentence_constraint(prompt),
        max_sentences=_constraint_integer(prompt, r"(?:at most|no more than|maximum(?: of)?)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+sentences?"),
        exact_items=_constraint_integer(prompt, r"exactly\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:items?|bullet(?: points?)?)"),
        max_items=_constraint_integer(
            prompt,
            r"(?:at most|no more than|maximum(?: of)?)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
            r"(?:items?|bullet(?: points?)?)",
        ),
    )


def apply_answer_contract(task: TaskEnvelope, answer: str) -> AnswerContractResult:
    contract = infer_answer_contract(task)
    original = answer.strip()
    if not original:
        return AnswerContractResult(False, "", original, "empty_answer", contract)

    if contract.kind is AnswerContractKind.LABEL:
        candidate, action, ambiguous = _normalize_label(original, contract.allowed_values)
        if not candidate:
            reason = "ambiguous_label" if ambiguous else "label_not_found"
            return AnswerContractResult(False, original, original, reason, contract, ambiguous=ambiguous)
        actions = (action,) if action else ()
    else:
        validation = validate_or_safely_repair_final_answer(task, original)
        if not validation.valid:
            return AnswerContractResult(
                False,
                original,
                original,
                validation.reason,
                contract,
                ambiguous=_is_ambiguous_repair(task, original, validation),
            )
        candidate = validation.repaired_answer or original
        actions = (validation.reason,) if validation.reason.startswith("safe_repair:") else ()

    normalized_shape, shape_actions = _normalize_json_object_shape(task.input_text, candidate, contract)
    if normalized_shape != candidate:
        candidate = normalized_shape
        actions = (*actions, *shape_actions)

    normalized_json = _normalize_singleton_json_values(task.input_text, candidate, contract)
    if normalized_json and normalized_json != candidate:
        candidate = normalized_json
        actions = (*actions, "unwrapped_singleton_json_values")

    if contract.strict and contract.exact_items is not None:
        normalized_list = _normalize_item_wrapper(candidate, contract.exact_items)
        if normalized_list and normalized_list != candidate:
            candidate = normalized_list
            actions = (*actions, "removed_list_preface")

    constraint_reason = _validate_contract_constraints(contract, candidate)
    if constraint_reason:
        return AnswerContractResult(False, candidate, original, constraint_reason, contract, actions)
    return AnswerContractResult(True, candidate, original, "contract_satisfied", contract, actions)


def finalize_answer_result(task: TaskEnvelope, result: AnswerResult) -> AnswerResult:
    application = apply_answer_contract(task, result.answer)
    final_answer = application.answer if application.valid else result.answer.strip()
    return AnswerResult(
        id=result.id,
        answer=final_answer,
        route=result.route,
        remote_tokens=result.remote_tokens,
        metadata={**result.metadata, "answer_contract": application.to_dict()},
    )


SAFE_REPAIR_REASONS = {
    "markdown_fence_in_strict_format",
    "invalid_json",
    "python_code_with_extra_text",
    "code_with_extra_text",
    "not_number_only",
    "not_yes_no",
    "not_uppercase",
    "literal_echo_mismatch",
}


def validate_final_answer(task: TaskEnvelope, answer: str) -> FinalValidationResult:
    expected_format = infer_expected_format(task)
    stripped = answer.strip()
    if not stripped:
        return FinalValidationResult(False, expected_format, "empty_answer")
    if expected_format != "free_text" and _has_markdown_fence(stripped):
        repaired = repair_final_answer(task, answer).repaired_answer
        return FinalValidationResult(False, expected_format, "markdown_fence_in_strict_format", repaired)
    if expected_format == "json":
        try:
            _strict_json_loads(stripped)
        except (json.JSONDecodeError, ValueError):
            repaired = repair_final_answer(task, answer).repaired_answer
            return FinalValidationResult(False, expected_format, "invalid_json", repaired)
        return FinalValidationResult(True, expected_format, "valid_json")
    if expected_format == "number":
        if _is_canonical_number(stripped):
            return FinalValidationResult(True, expected_format, "valid_number")
        repaired = repair_final_answer(task, answer).repaired_answer
        return FinalValidationResult(False, expected_format, "not_number_only", repaired)
    if expected_format == "literal_echo":
        expected = extract_literal_echo(task)
        if stripped == expected:
            return FinalValidationResult(True, expected_format, "valid_literal_echo")
        return FinalValidationResult(False, expected_format, "literal_echo_mismatch", expected)
    if expected_format == "yes_no":
        if stripped.lower() in {"yes", "no"}:
            return FinalValidationResult(True, expected_format, "valid_yes_no")
        repaired = repair_final_answer(task, answer).repaired_answer
        return FinalValidationResult(False, expected_format, "not_yes_no", repaired)
    if expected_format == "uppercase":
        if stripped == stripped.upper():
            return FinalValidationResult(True, expected_format, "valid_uppercase")
        return FinalValidationResult(False, expected_format, "not_uppercase", stripped.upper())
    if expected_format == "code":
        repaired = repair_final_answer(task, answer).repaired_answer
        if _has_markdown_fence(stripped):
            return FinalValidationResult(False, expected_format, "markdown_fence_in_code", repaired)
        if _looks_like_python_code_task(task):
            if _is_valid_python(stripped):
                if _unsafe_python_construct(stripped):
                    return FinalValidationResult(False, expected_format, "unsafe_python_construct")
                return FinalValidationResult(True, expected_format, "valid_python_code")
            if repaired and repaired != stripped and _is_valid_python(repaired):
                return FinalValidationResult(False, expected_format, "python_code_with_extra_text", repaired)
            return FinalValidationResult(False, expected_format, "invalid_python_code", repaired)
        if repaired and repaired != stripped:
            return FinalValidationResult(False, expected_format, "code_with_extra_text", repaired)
        return FinalValidationResult(True, expected_format, "valid_code")
    degradation = _free_text_degradation(stripped)
    if degradation:
        return FinalValidationResult(False, expected_format, degradation)
    return FinalValidationResult(True, expected_format, "valid_free_text")


def validate_or_safely_repair_final_answer(task: TaskEnvelope, answer: str) -> FinalValidationResult:
    initial = validate_final_answer(task, answer)
    if initial.valid or initial.reason not in SAFE_REPAIR_REASONS or not initial.repaired_answer:
        return initial
    if initial.expected_format == "number" and initial.reason in {"markdown_fence_in_strict_format", "not_number_only"}:
        unfenced = _strip_markdown_fence(answer.strip())
        numbers = _numeric_candidates(unfenced)
        if len(numbers) != 1:
            return initial
    repaired = validate_final_answer(task, initial.repaired_answer)
    if not repaired.valid:
        return initial
    return FinalValidationResult(
        True,
        initial.expected_format,
        f"safe_repair:{initial.reason}",
        initial.repaired_answer,
    )


def repair_final_answer(task: TaskEnvelope, answer: str) -> FinalValidationResult:
    expected_format = infer_expected_format(task)
    stripped = _strip_markdown_fence(answer.strip())
    if expected_format == "json":
        extracted = _extract_single_json_value(stripped)
        return FinalValidationResult(bool(extracted), expected_format, "json_repair", extracted)
    if expected_format == "number":
        candidates = _numeric_candidates(stripped)
        repaired = _canonicalize_number(candidates[0]) if len(candidates) == 1 else ""
        return FinalValidationResult(bool(repaired), expected_format, "number_repair", repaired)
    if expected_format == "literal_echo":
        expected = extract_literal_echo(task)
        return FinalValidationResult(bool(expected), expected_format, "literal_echo_repair", expected)
    if expected_format == "yes_no":
        lowered = stripped.lower()
        if re.search(r"\b(?:not|isn't|isnt|never)\s+(?:yes|no)\b", lowered):
            return FinalValidationResult(False, expected_format, "yes_no_repair", "")
        yes = bool(re.search(r"\byes\b", lowered))
        no = bool(re.search(r"\bno\b", lowered))
        repaired = "yes" if yes and not no else "no" if no and not yes else ""
        return FinalValidationResult(bool(repaired), expected_format, "yes_no_repair", repaired)
    if expected_format == "uppercase":
        return FinalValidationResult(bool(stripped), expected_format, "uppercase_repair", stripped.upper())
    if expected_format == "code":
        repaired = _repair_code_answer(task, stripped)
        return FinalValidationResult(bool(repaired), expected_format, "code_repair", repaired)
    return FinalValidationResult(bool(stripped), expected_format, "free_text_repair", stripped)


def _has_markdown_fence(value: str) -> bool:
    return value.startswith("```") or value.endswith("```")


def _strip_markdown_fence(value: str) -> str:
    if not _has_markdown_fence(value):
        return value
    stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", value)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _extract_single_json_value(value: str) -> str:
    stripped = _strip_markdown_fence(value)
    try:
        _strict_json_loads(stripped)
    except (json.JSONDecodeError, ValueError):
        pass
    else:
        return stripped

    maximal = _embedded_json_values(stripped)
    return maximal[0] if len(maximal) == 1 else ""


def _embedded_json_values(value: str) -> list[str]:
    decoder = json.JSONDecoder(object_pairs_hook=_reject_duplicate_json_keys, parse_constant=_reject_json_constant)
    spans: list[tuple[int, int, str]] = []
    for start, char in enumerate(value):
        if char not in "[{":
            continue
        try:
            _, length = decoder.raw_decode(value[start:])
        except (json.JSONDecodeError, ValueError):
            continue
        spans.append((start, start + length, value[start : start + length]))

    maximal = [
        span
        for span in spans
        if not any(
            other[0] <= span[0] and span[1] <= other[1] and (other[0], other[1]) != (span[0], span[1])
            for other in spans
        )
    ]
    return [span[2] for span in maximal]


_NUMBER_PATTERN = re.compile(
    r"(?<![\w.])[-+]?(?:(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?)|(?:\d+(?:\.\d+)?)|(?:\.\d+))"
    r"(?:[eE][-+]?\d+)?(?!\w|\.\d)"
)


def _numeric_candidates(value: str) -> list[str]:
    return [match.group(0) for match in _NUMBER_PATTERN.finditer(value)]


def _canonicalize_number(value: str) -> str:
    normalized = value.replace(",", "")
    return normalized[1:] if normalized.startswith("+") else normalized


def _is_canonical_number(value: str) -> bool:
    candidates = _numeric_candidates(value)
    return len(candidates) == 1 and _canonicalize_number(candidates[0]) == value


def _repair_code_answer(task: TaskEnvelope, value: str) -> str:
    stripped = _strip_markdown_fence(value.strip())
    if not stripped:
        return ""
    fenced = _extract_fenced_code(stripped)
    if fenced:
        stripped = fenced
    python_like = _looks_like_python_code_task(task) or _contains_python_code_anchor(stripped)
    if python_like:
        normalized = _normalize_code(stripped)
        if _is_valid_python(normalized):
            return normalized
        extracted = _extract_python_code_block(normalized)
        if extracted and _is_valid_python(extracted):
            return extracted
        return ""
    generic = _extract_generic_code_block(stripped)
    return generic or stripped


def _looks_like_python_code_task(task: TaskEnvelope) -> bool:
    text = task.input_text.lower()
    if "python" in text:
        return True
    if re.search(r"\bdef\s+[a-zA-Z_]\w*\s*\(", task.input_text):
        return True
    if "corrected implementation" in text and re.search(r"\b(debug|bug|fix|broken)\b", text):
        return True
    if re.search(r"\b(write|define|implement|create)\b.*\bfunction\b", text) and "return only code" in text:
        return True
    return False


def _contains_python_code_anchor(value: str) -> bool:
    return bool(
        re.search(r"```(?:python|py)\b", value, re.IGNORECASE)
        or re.search(r"(?m)^\s*(?:async\s+def|def|class)\s+[a-zA-Z_]\w*\s*[\(:]", value)
        or re.search(r"(?m)^\s*(?:from\s+\w[\w.]*\s+import|import\s+\w)", value)
    )


def _unsafe_python_construct(value: str) -> bool:
    try:
        tree = ast.parse(value)
    except (SyntaxError, ValueError, TypeError):
        return True
    blocked_nodes = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)
    blocked_names = {"__import__", "eval", "exec", "compile", "open", "input", "breakpoint"}
    return any(
        isinstance(node, blocked_nodes)
        or isinstance(node, ast.Name) and node.id in blocked_names
        for node in ast.walk(tree)
    )


def _extract_fenced_code(value: str) -> str:
    match = re.search(r"```(?:python|py|[a-zA-Z0-9_-]+)?\s*(.*?)```", value, re.DOTALL)
    if not match:
        return ""
    return _normalize_code(match.group(1))


def _extract_python_code_block(value: str) -> str:
    lines = value.splitlines()
    starts = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^\s*(?:@|async\s+def\b|def\b|class\b|from\s+\w|import\s+\w)", line)
    ]
    for start in starts:
        for end in range(len(lines), start, -1):
            candidate = _normalize_code("\n".join(lines[start:end]))
            if candidate and _is_valid_python(candidate):
                return candidate
    return ""


def _extract_generic_code_block(value: str) -> str:
    lines = value.splitlines()
    for index, line in enumerate(lines):
        if re.match(
            r"^\s*(?:function|const|let|var|export|class|public|private|#include|SELECT|WITH)\b",
            line,
            re.IGNORECASE,
        ):
            return "\n".join(lines[index:]).strip()
    return ""


def _normalize_code(value: str) -> str:
    return textwrap.dedent(value).strip()


def _is_valid_python(value: str) -> bool:
    try:
        ast.parse(value)
    except SyntaxError:
        return False
    return bool(value.strip())


def _free_text_degradation(value: str) -> str:
    # These checks intentionally target only high-confidence corruption. Natural
    # lists and short answers often omit terminal punctuation and remain valid.
    if value.count("```") % 2:
        return "unclosed_markdown_fence"
    tokens = re.findall(r"[\w'-]+", value.casefold())
    if len(tokens) < 16:
        return ""
    for width in (6, 5, 4):
        counts: dict[tuple[str, ...], int] = {}
        for index in range(len(tokens) - width + 1):
            gram = tuple(tokens[index : index + width])
            counts[gram] = counts.get(gram, 0) + 1
        if counts and max(counts.values()) >= 4:
            return "degenerate_repetition"
    return ""


def _extract_allowed_labels(prompt: str) -> tuple[str, ...]:
    lowered = prompt.casefold()
    strict_sentiment = bool(
        re.search(r"\bclassif(?:y|ique|ica)\b.*\b(?:as|como)\b", lowered)
        or re.search(r"\b(?:answer|return|respond)\b.*\b(?:only|exactly one)\b.*\blabel\b", lowered)
    ) and not re.search(
        r"\b(?:explain|explanation|justify|justification|assessment|analysis|reason|reasoning|rationale)\b",
        lowered,
    )
    if strict_sentiment and all(label in lowered for label in ("positive", "negative", "neutral")):
        labels = ["positive", "negative", "neutral"]
        if re.search(r"\bmixed\b", lowered):
            labels.append("mixed")
        return tuple(labels)
    matches = (
        re.search(r"(?:one\s+)?label\s*:\s*([^\n.?!]+)", prompt, re.IGNORECASE),
        re.search(
            r"(?:choose|select|answer with|return)\s+(?:exactly\s+)?one\s+(?:of|from)\s*:?\s*([^\n.?!]+)",
            prompt,
            re.IGNORECASE,
        ),
    )
    match = next((item for item in matches if item), None)
    if match is None:
        return ()
    raw = re.sub(r"\s+or\s+", ",", match.group(1), flags=re.IGNORECASE)
    values: list[str] = []
    for item in raw.split(","):
        value = item.strip().strip("\"'` ")
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9 _-]{0,39}", value):
            values.append(value)
    return tuple(dict.fromkeys(values)) if len(values) >= 2 else ()


def _extract_json_keys(prompt: str) -> tuple[str, ...]:
    marker = re.search(r"\b(?:exactly\s+)?(?:these\s+)?(keys?)\b", prompt, re.IGNORECASE)
    if marker is None:
        return ()
    tail = prompt[marker.end() : marker.end() + 300]
    keys = re.findall(r"[\"']([A-Za-z_][A-Za-z0-9_-]{0,63})[\"']", tail)
    if marker.group(1).casefold() == "key":
        if keys:
            return (keys[0],)
        singular = re.match(r"\s*(?:is|:)?\s*([A-Za-z_][A-Za-z0-9_-]{0,63})", tail)
        return (singular.group(1),) if singular else ()
    if not keys:
        compact = re.match(
            r"\s*(?:are|:)?\s*([A-Za-z_][A-Za-z0-9_-]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_-]*)+)",
            tail,
        )
        keys = [item.strip() for item in compact.group(1).split(",")] if compact else []
    return tuple(dict.fromkeys(keys))


def _constraint_integer(prompt: str, pattern: str) -> int | None:
    match = re.search(pattern, prompt, re.IGNORECASE)
    if match is None:
        return None
    raw = match.group(1).casefold()
    words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    return int(raw) if raw.isdigit() else words[raw]


def _exact_sentence_constraint(prompt: str) -> int | None:
    if re.search(
        r"\b(?:exactly\s+(?:the\s+)?(?:single|one)|in\s+(?:exactly\s+)?(?:one|a single))\s+sentence\b",
        prompt,
        re.IGNORECASE,
    ):
        return 1
    return _constraint_integer(
        prompt,
        r"exactly\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+sentences?",
    )


def _normalize_label(answer: str, allowed_values: tuple[str, ...]) -> tuple[str, str, bool]:
    candidate = _strip_markdown_fence(answer.strip()).strip(" \t\r\n.\"'`")
    by_folded = {value.casefold(): value for value in allowed_values}
    if candidate.casefold() in by_folded:
        normalized = by_folded[candidate.casefold()]
        action = "canonicalized_label" if normalized != answer.strip() else ""
        return normalized, action, False
    found: list[str] = []
    for folded, canonical in by_folded.items():
        pattern = rf"(?<![\w-]){re.escape(folded)}(?![\w-])"
        for match in re.finditer(pattern, candidate.casefold()):
            prefix = candidate.casefold()[max(0, match.start() - 16) : match.start()]
            if re.search(r"\b(?:not|isn't|is not|never)\s*$", prefix):
                return "", "", True
            found.append(canonical)
    unique = tuple(dict.fromkeys(found))
    if len(unique) != 1:
        return "", "", len(unique) > 1
    return unique[0], "extracted_unique_label", False


def _normalize_singleton_json_values(
    prompt: str,
    answer: str,
    contract: AnswerContract,
) -> str:
    if contract.kind is not AnswerContractKind.JSON or not contract.json_keys:
        return answer
    if re.search(r"\b(?:array|arrays|list|lists|multiple|all values|zero or more)\b", prompt, re.IGNORECASE):
        return answer
    if any(_looks_plural_json_key(key) for key in contract.json_keys):
        return answer
    try:
        payload = _strict_json_loads(answer)
    except (json.JSONDecodeError, ValueError):
        return answer
    if not isinstance(payload, dict) or set(payload) != set(contract.json_keys):
        return answer
    if not payload or not all(
        isinstance(value, list)
        and len(value) == 1
        and isinstance(value[0], (str, int, float, bool))
        for value in payload.values()
    ):
        return answer
    normalized = {key: value[0] for key, value in payload.items()}
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


def _normalize_json_object_shape(
    prompt: str,
    answer: str,
    contract: AnswerContract,
) -> tuple[str, tuple[str, ...]]:
    if contract.kind is not AnswerContractKind.JSON or not contract.json_keys:
        return answer, ()
    try:
        payload = _strict_json_loads(answer)
    except (json.JSONDecodeError, ValueError):
        return answer, ()
    actions: list[str] = []
    if (
        isinstance(payload, list)
        and len(payload) == 1
        and isinstance(payload[0], dict)
        and not re.search(r"\b(?:array|arrays|list|lists|multiple|all entities|zero or more)\b", prompt, re.IGNORECASE)
    ):
        payload = payload[0]
        actions.append("unwrapped_singleton_json_object_array")
    if not isinstance(payload, dict):
        return answer, ()
    expected_by_folded = {key.casefold(): key for key in contract.json_keys}
    observed_folded = [str(key).casefold() for key in payload]
    if (
        len(observed_folded) == len(set(observed_folded))
        and set(observed_folded) == set(expected_by_folded)
        and set(payload) != set(contract.json_keys)
    ):
        payload = {expected_by_folded[str(key).casefold()]: value for key, value in payload.items()}
        actions.append("canonicalized_json_key_case")
    if not actions:
        return answer, ()
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")), tuple(actions)


def _strict_json_loads(value: str) -> Any:
    return json.loads(
        value,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_json_constant,
    )


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"Duplicate JSON key: {key}")
        payload[key] = value
    return payload


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-standard JSON constant: {value}")


def _looks_plural_json_key(key: str) -> bool:
    lowered = key.casefold().replace("-", "_")
    plural_terms = {
        "entities",
        "items",
        "people",
        "persons",
        "locations",
        "organizations",
        "results",
        "values",
    }
    return lowered in plural_terms or lowered.endswith("_list") or lowered.endswith("_items")


def _validate_contract_constraints(contract: AnswerContract, answer: str) -> str:
    if contract.kind is AnswerContractKind.JSON and contract.json_keys:
        try:
            payload = _strict_json_loads(answer)
        except (json.JSONDecodeError, ValueError):
            return "invalid_json_after_normalization"
        if not isinstance(payload, dict) or set(payload) != set(contract.json_keys):
            return "json_keys_mismatch"
    words = re.findall(r"[A-Za-zÀ-ÿ0-9_'-]+", answer)
    if contract.exact_words is not None and len(words) != contract.exact_words:
        return "exact_word_count_mismatch"
    if contract.max_words is not None and len(words) > contract.max_words:
        return "maximum_word_count_exceeded"
    sentences = _sentence_count(answer)
    if contract.exact_sentences is not None and sentences != contract.exact_sentences:
        return "exact_sentence_count_mismatch"
    if contract.max_sentences is not None and sentences > contract.max_sentences:
        return "maximum_sentence_count_exceeded"
    if contract.exact_items is not None and _item_count(answer) != contract.exact_items:
        return "exact_item_count_mismatch"
    if contract.max_items is not None and _item_count(answer) > contract.max_items:
        return "maximum_item_count_exceeded"
    return ""


def _sentence_count(value: str) -> int:
    stripped = value.strip()
    if not stripped:
        return 0
    return len([item for item in re.split(r"(?<=[.!?])(?:\s+|$)", stripped) if item.strip()])


def _item_count(value: str) -> int:
    bullets = re.findall(r"(?m)^\s*(?:[-*+] |\d+[.)]\s+)", value)
    if bullets:
        return len(bullets)
    try:
        payload = _strict_json_loads(value)
    except (json.JSONDecodeError, ValueError):
        return 0
    return len(payload) if isinstance(payload, list) else 0


def _normalize_item_wrapper(value: str, expected_items: int) -> str:
    lines = value.splitlines()
    indexes = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^\s*(?:[-*+] |\d+[.)]\s+)", line)
    ]
    if len(indexes) != expected_items or not indexes or indexes[0] == 0:
        return value
    return "\n".join(lines[indexes[0] :]).strip()


def _is_ambiguous_repair(
    task: TaskEnvelope,
    answer: str,
    validation: FinalValidationResult,
) -> bool:
    del task
    if validation.expected_format == "number":
        return len(_numeric_candidates(answer)) != 1
    if validation.expected_format == "json":
        return len(_embedded_json_values(_strip_markdown_fence(answer.strip()))) > 1
    if validation.expected_format == "yes_no":
        lowered = answer.casefold()
        return bool(re.search(r"\byes\b", lowered)) == bool(re.search(r"\bno\b", lowered))
    return False
