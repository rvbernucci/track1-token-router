from __future__ import annotations

import json

from router.core.contracts import AnswerResult, TaskEnvelope


class FilePayloadAdapter:
    name = "file_payload"

    def parse(self, raw: str) -> list[TaskEnvelope]:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("file_payload adapter expects one JSON object.")
        if "files" not in payload:
            payload["files"] = [
                {
                    "name": payload.get("name", "input.txt"),
                    "path": payload.get("path", ""),
                    "mime_type": payload.get("mime_type", "application/octet-stream"),
                }
            ]
        return [TaskEnvelope.from_mapping(payload)]

    def format(self, results: list[AnswerResult]) -> str:
        if len(results) != 1:
            raise ValueError("file_payload adapter expects exactly one result.")
        return results[0].to_json()
