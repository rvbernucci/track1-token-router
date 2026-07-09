from __future__ import annotations

import json
import re
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
        if _has_markdown_fence(stripped):
            repaired = repair_final_answer(task, answer).repaired_answer
            return FinalValidationResult(False, expected_format, "markdown_fence_in_code", repaired)
        return FinalValidationResult(True, expected_format, "valid_code")
    return FinalValidationResult(True, expected_format, "valid_free_text")


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
        return FinalValidationResult(bool(stripped), expected_format, "code_repair", stripped)
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
