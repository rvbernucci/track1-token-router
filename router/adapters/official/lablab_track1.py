from __future__ import annotations

import json
from typing import Any

from router.core.contracts import AnswerResult, TaskEnvelope


class LablabTrack1Adapter:
    name = "lablab_track1"

    def parse(self, raw: str) -> list[TaskEnvelope]:
        payload = json.loads(raw)
        if not isinstance(payload, list):
            raise ValueError("lablab_track1 adapter expects /input/tasks.json to be a JSON array.")

        tasks: list[TaskEnvelope] = []
        for index, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"lablab_track1 task {index} must be an object.")
            task_id = item.get("task_id")
            prompt = item.get("prompt")
            if not isinstance(task_id, str) or not task_id.strip():
                raise ValueError(f"lablab_track1 task {index} is missing task_id.")
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError(f"lablab_track1 task {task_id} is missing prompt.")
            metadata: dict[str, Any] = {
                "adapter": self.name,
                "official_contract": "amd_developer_hackathon_act_ii_track1",
            }
            tasks.append(TaskEnvelope(id=task_id, input_text=prompt, metadata=metadata))
        return tasks

    def format(self, results: list[AnswerResult]) -> str:
        payload = [
            {
                "task_id": result.id or f"task-{index}",
                "answer": result.answer,
            }
            for index, result in enumerate(results, start=1)
        ]
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
