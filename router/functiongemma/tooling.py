from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from router.core.contracts import Intent, TaskAssessment


DEVELOPER_INSTRUCTION = "Call assess_task exactly once. Assess the task; never answer it or select an engine."
SCORE_FIELDS = (
    "deterministic_fit",
    "reasoning_demand",
    "knowledge_uncertainty",
    "generation_demand",
    "format_complexity",
)
FUNCTIONGEMMA_GENERATION_STOP_TOKENS = ("<end_function_call>", "<start_function_response>")


ASSESS_TASK_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "assess_task",
        "description": (
            "Classify a Track 1 task and score its execution demands. "
            "Do not answer the task and do not select an engine or model."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "intent": {"type": "string", "enum": [intent.value for intent in Intent]},
                "scores": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        name: {"type": "integer", "minimum": 0, "maximum": 10}
                        for name in SCORE_FIELDS
                    },
                    "required": list(SCORE_FIELDS),
                },
            },
            "required": ["intent", "scores"],
        },
    },
}


def training_conversation(task_text: str, assessment: TaskAssessment) -> dict[str, Any]:
    if not isinstance(task_text, str) or not task_text.strip():
        raise ValueError("task_text must be a non-empty string.")
    return {
        "messages": [
            {"role": "developer", "content": DEVELOPER_INSTRUCTION},
            {"role": "user", "content": task_text},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "assess_task",
                            "arguments": {
                                "intent": assessment.intent.value,
                                "scores": assessment.scores.to_dict(),
                            },
                        },
                    }
                ],
            },
        ],
        "tools": [ASSESS_TASK_TOOL],
    }


def validate_training_row(payload: Mapping[str, Any]) -> TaskAssessment:
    messages = payload.get("messages")
    if not isinstance(messages, list) or len(messages) != 3:
        raise ValueError("Training row must contain exactly developer, user and assistant messages.")
    if messages[0] != {"role": "developer", "content": DEVELOPER_INSTRUCTION}:
        raise ValueError("Training row has a non-canonical developer instruction.")
    if messages[1].get("role") != "user" or not isinstance(messages[1].get("content"), str):
        raise ValueError("Training row must contain a non-empty user task.")
    assistant = messages[2]
    calls = assistant.get("tool_calls") if isinstance(assistant, Mapping) else None
    if assistant.get("role") != "assistant" or not isinstance(calls, list) or len(calls) != 1:
        raise ValueError("Training row must contain exactly one assistant tool call.")
    call = calls[0]
    function = call.get("function") if isinstance(call, Mapping) else None
    if call.get("type") != "function" or not isinstance(function, Mapping):
        raise ValueError("Training row tool call is malformed.")
    if function.get("name") != "assess_task" or not isinstance(function.get("arguments"), Mapping):
        raise ValueError("Training row must call assess_task with object arguments.")
    parsed = TaskAssessment.from_mapping(function["arguments"])
    if parsed.sub_intent is not None:
        raise ValueError("FunctionGemma training output must not contain sub_intent.")
    return parsed


def assessment_from_function_call(text: str) -> TaskAssessment:
    """Parse one FunctionGemma native call and reject all extra model output."""
    start_token = "<start_function_call>"
    end_token = "<end_function_call>"
    if text.count(start_token) != 1 or text.count(end_token) != 1:
        raise ValueError("Expected exactly one complete function call.")
    prefix, remainder = text.split(start_token, 1)
    body, suffix = remainder.split(end_token, 1)
    if prefix.strip() or suffix.strip() not in {"", "<end_of_turn>"}:
        raise ValueError("Function call output contains additional text.")
    marker = "call:assess_task"
    if not body.startswith(marker):
        raise ValueError("Model did not call assess_task.")
    parser = _FunctionGemmaValueParser(body[len(marker) :])
    value = parser.parse_value()
    parser.require_end()
    if not isinstance(value, Mapping):
        raise ValueError("assess_task arguments must be an object.")
    assessment = TaskAssessment.from_mapping(value)
    if assessment.sub_intent is not None:
        raise ValueError("FunctionGemma output must not contain sub_intent.")
    return assessment


def generation_eos_token_ids(tokenizer: Any) -> list[int]:
    """Return normal EOS plus FunctionGemma interception boundaries."""
    token_ids: list[int] = []
    normal_eos = getattr(tokenizer, "eos_token_id", None)
    if isinstance(normal_eos, int) and normal_eos >= 0:
        token_ids.append(normal_eos)
    unknown = getattr(tokenizer, "unk_token_id", None)
    for token in FUNCTIONGEMMA_GENERATION_STOP_TOKENS:
        token_id = tokenizer.convert_tokens_to_ids(token)
        if not isinstance(token_id, int) or token_id < 0 or token_id == unknown:
            raise ValueError(f"Tokenizer does not define required FunctionGemma stop token {token!r}.")
        token_ids.append(token_id)
    return list(dict.fromkeys(token_ids))


class _FunctionGemmaValueParser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.offset = 0

    def parse_value(self) -> Any:
        self._skip_space()
        if self._peek("{"):
            return self._parse_object()
        if self._peek("["):
            return self._parse_array()
        if self._peek("<escape>"):
            return self._parse_string()
        return self._parse_number()

    def _parse_object(self) -> dict[str, Any]:
        self._consume("{")
        result: dict[str, Any] = {}
        self._skip_space()
        if self._peek("}"):
            self._consume("}")
            return result
        while True:
            key = self._parse_key()
            if key in result:
                raise ValueError(f"Duplicate function argument {key!r}.")
            self._consume(":")
            result[key] = self.parse_value()
            self._skip_space()
            if self._peek("}"):
                self._consume("}")
                return result
            self._consume(",")

    def _parse_array(self) -> list[Any]:
        self._consume("[")
        values: list[Any] = []
        self._skip_space()
        if self._peek("]"):
            self._consume("]")
            return values
        while True:
            values.append(self.parse_value())
            self._skip_space()
            if self._peek("]"):
                self._consume("]")
                return values
            self._consume(",")

    def _parse_string(self) -> str:
        self._consume("<escape>")
        end = self.text.find("<escape>", self.offset)
        if end < 0:
            raise ValueError("Unterminated escaped string.")
        value = self.text[self.offset : end]
        self.offset = end + len("<escape>")
        return value

    def _parse_number(self) -> int | float:
        start = self.offset
        if self._peek("-"):
            self.offset += 1
        while self.offset < len(self.text) and self.text[self.offset].isdigit():
            self.offset += 1
        if self.offset < len(self.text) and self.text[self.offset] == ".":
            self.offset += 1
            decimal_start = self.offset
            while self.offset < len(self.text) and self.text[self.offset].isdigit():
                self.offset += 1
            if self.offset == decimal_start:
                raise ValueError(f"Invalid decimal function value at offset {start}.")
        token = self.text[start : self.offset]
        if not token or token == "-":
            raise ValueError(f"Unsupported function value at offset {start}.")
        return float(token) if "." in token else int(token)

    def _parse_key(self) -> str:
        self._skip_space()
        start = self.offset
        while self.offset < len(self.text) and (self.text[self.offset].isalnum() or self.text[self.offset] == "_"):
            self.offset += 1
        if self.offset == start:
            raise ValueError(f"Expected object key at offset {start}.")
        return self.text[start : self.offset]

    def _skip_space(self) -> None:
        while self.offset < len(self.text) and self.text[self.offset].isspace():
            self.offset += 1

    def _peek(self, token: str) -> bool:
        self._skip_space()
        return self.text.startswith(token, self.offset)

    def _consume(self, token: str) -> None:
        self._skip_space()
        if not self.text.startswith(token, self.offset):
            raise ValueError(f"Expected {token!r} at offset {self.offset}.")
        self.offset += len(token)

    def require_end(self) -> None:
        self._skip_space()
        if self.offset != len(self.text):
            raise ValueError(f"Unexpected trailing function syntax at offset {self.offset}.")


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_number} must contain an object.")
            rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
