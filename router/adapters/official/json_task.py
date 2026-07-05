from __future__ import annotations

import json

from router.core.contracts import AnswerResult, TaskEnvelope


class JsonTaskAdapter:
    name = "json_task"

    def parse(self, raw: str) -> list[TaskEnvelope]:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("json_task adapter expects one JSON object.")
        return [TaskEnvelope.from_mapping(payload)]

    def format(self, results: list[AnswerResult]) -> str:
        if len(results) != 1:
            raise ValueError("json_task adapter expects exactly one result.")
        return results[0].to_json()
