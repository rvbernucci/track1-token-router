from __future__ import annotations

import ast
import json
import re
import textwrap
from dataclasses import asdict, dataclass

from router.core.contracts import TaskEnvelope
from router.orchestration.prompt_packet import extract_literal_echo, infer_expected_format


@dataclass(frozen=True)
class FinalValidationResult:
    valid: bool
    expected_format: str
    reason: str
    repaired_answer: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


SAFE_REPAIR_REASONS = {
    "markdown_fence_in_strict_format",
    "invalid_json",
    "python_code_with_extra_text",
    "code_with_extra_text",
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
            json.loads(stripped)
        except json.JSONDecodeError:
            repaired = repair_final_answer(task, answer).repaired_answer
            return FinalValidationResult(False, expected_format, "invalid_json", repaired)
        return FinalValidationResult(True, expected_format, "valid_json")
    if expected_format == "number":
        if re.fullmatch(r"-?\d+(?:\.\d+)?", stripped):
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
    if initial.reason == "markdown_fence_in_strict_format" and initial.expected_format == "number":
        unfenced = _strip_markdown_fence(answer.strip())
        if not re.fullmatch(r"-?\d+(?:\.\d+)?", unfenced):
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
        extracted = _extract_json_object(stripped)
        return FinalValidationResult(bool(extracted), expected_format, "json_repair", extracted)
    if expected_format == "number":
        match = re.search(r"-?\d+(?:\.\d+)?", stripped)
        repaired = match.group(0) if match else ""
        return FinalValidationResult(bool(repaired), expected_format, "number_repair", repaired)
    if expected_format == "literal_echo":
        expected = extract_literal_echo(task)
        return FinalValidationResult(bool(expected), expected_format, "literal_echo_repair", expected)
    if expected_format == "yes_no":
        lowered = stripped.lower()
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


def _extract_json_object(value: str) -> str:
    stripped = _strip_markdown_fence(value)
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ""
    return stripped[start : end + 1]


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
