from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FileAttachment:
    name: str
    path: str
    mime_type: str | None = None

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "FileAttachment":
        return cls(
            name=str(payload.get("name") or payload.get("filename") or ""),
            path=str(payload.get("path") or ""),
            mime_type=payload.get("mime_type") or payload.get("mime"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "mime_type": self.mime_type,
        }


@dataclass(frozen=True)
class TaskEnvelope:
    input_text: str
    id: str | None = None
    files: list[FileAttachment] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "TaskEnvelope":
        input_text = _coerce_input_text(payload)
        files_payload = payload.get("files") or []
        if not isinstance(files_payload, list):
            raise ValueError("TaskEnvelope.files must be a list.")
        metadata = payload.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ValueError("TaskEnvelope.metadata must be an object.")
        return cls(
            id=_optional_str(payload.get("id")),
            input_text=input_text,
            files=[
                FileAttachment.from_mapping(item)
                for item in files_payload
                if isinstance(item, dict)
            ],
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "input_text": self.input_text,
            "files": [file.to_dict() for file in self.files],
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class TokenUsage:
    prompt: int = 0
    completion: int = 0
    total: int = 0

    @classmethod
    def empty(cls) -> "TokenUsage":
        return cls()

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt": self.prompt,
            "completion": self.completion,
            "total": self.total,
        }


@dataclass(frozen=True)
class RouteDecision:
    route: str
    decision: str
    reason: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "route": self.route,
            "decision": self.decision,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    route: str
    id: str | None = None
    remote_tokens: TokenUsage = field(default_factory=TokenUsage.empty)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "answer": self.answer,
            "route": self.route,
            "remote_tokens": self.remote_tokens.to_dict(),
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


def _coerce_input_text(payload: dict[str, Any]) -> str:
    for key in ("input_text", "question", "prompt", "input", "text"):
        value = payload.get(key)
        if value is not None:
            if isinstance(value, str):
                return value
            return json.dumps(value, ensure_ascii=False)
    raise ValueError("TaskEnvelope requires one of: input_text, question, prompt, input, text.")


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)

