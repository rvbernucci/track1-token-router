from __future__ import annotations

import json

from router.core.contracts import AnswerResult, TaskEnvelope


class JsonlBatchAdapter:
    name = "jsonl_batch"

    def parse(self, raw: str) -> list[TaskEnvelope]:
        tasks: list[TaskEnvelope] = []
        for line_number, line in enumerate(raw.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, dict):
                raise ValueError(f"jsonl_batch line {line_number} must be an object.")
            tasks.append(TaskEnvelope.from_mapping(payload))
        return tasks

    def format(self, results: list[AnswerResult]) -> str:
        return "\n".join(result.to_json() for result in results)
