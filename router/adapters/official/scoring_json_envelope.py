from __future__ import annotations

import json
from typing import Any

from router.core.contracts import AnswerResult, TaskEnvelope


class ScoringJsonEnvelopeAdapter:
    name = "scoring_json_envelope"

    def parse(self, raw: str) -> list[TaskEnvelope]:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("scoring_json_envelope adapter expects one JSON object.")
        tasks_payload = payload.get("tasks")
        if not isinstance(tasks_payload, list):
            raise ValueError("scoring_json_envelope requires a tasks list.")

        tasks: list[TaskEnvelope] = []
        for index, item in enumerate(tasks_payload, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"scoring_json_envelope task {index} must be an object.")
            task_id = item.get("task_id") or item.get("id") or f"task-{index}"
            prompt = item.get("prompt") or item.get("question") or item.get("input_text")
            if not isinstance(prompt, str):
                raise ValueError(f"scoring_json_envelope task {task_id} is missing prompt text.")
            metadata: dict[str, Any] = {
                "adapter": self.name,
                "run_id": payload.get("run_id"),
                "scoring": payload.get("scoring", {}),
                "difficulty": item.get("difficulty"),
            }
            tasks.append(TaskEnvelope(id=str(task_id), input_text=prompt, metadata=metadata))
        return tasks

    def format(self, results: list[AnswerResult]) -> str:
        payload = {
            "answers": [
                {
                    "id": result.id,
                    "answer": result.answer,
                }
                for result in results
            ]
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
