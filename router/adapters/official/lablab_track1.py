from __future__ import annotations

import json
from typing import Any

from router.core.contracts import AnswerResult, TaskEnvelope


class LablabTrack1Adapter:
    name = "lablab_track1"

    def parse(self, raw: str) -> list[TaskEnvelope]:
        payload = json.loads(raw)
        tasks_payload, envelope_metadata = _coerce_tasks_payload(payload)

        tasks: list[TaskEnvelope] = []
        for index, item in enumerate(tasks_payload, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"lablab_track1 task {index} must be an object.")
            task_id = _coerce_task_id(item, index)
            prompt = _coerce_prompt(item)
            if not prompt.value.strip():
                raise ValueError(f"lablab_track1 task {task_id.value} is missing prompt text.")
            metadata: dict[str, Any] = {
                "adapter": self.name,
                "official_contract": "amd_developer_hackathon_act_ii_track1",
                "input_shape": envelope_metadata["input_shape"],
                "source_id_field": task_id.source_field,
                "source_prompt_field": prompt.source_field,
            }
            metadata.update(envelope_metadata["metadata"])
            if isinstance(item.get("metadata"), dict):
                metadata.update(item["metadata"])
            for key in ("category", "domain", "difficulty", "track", "validator"):
                if key in item:
                    metadata[key] = item[key]
            tasks.append(TaskEnvelope(id=task_id.value, input_text=prompt.value.strip(), metadata=metadata))
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


class _CoercedValue:
    def __init__(self, value: str, source_field: str) -> None:
        self.value = value
        self.source_field = source_field


def _coerce_tasks_payload(payload: Any) -> tuple[list[Any], dict[str, Any]]:
    if isinstance(payload, list):
        return payload, {"input_shape": "array", "metadata": {}}
    if not isinstance(payload, dict):
        raise ValueError("lablab_track1 adapter expects /input/tasks.json to be a JSON array or object with tasks.")

    for key in ("tasks", "items", "questions", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            metadata = {
                "run_id": payload.get("run_id") or payload.get("id"),
                "scoring": payload.get("scoring", {}),
                "output_contract": payload.get("output_contract", {}),
            }
            return value, {"input_shape": f"object.{key}", "metadata": metadata}
    raise ValueError("lablab_track1 object input requires one list field: tasks, items, questions, or data.")


def _coerce_task_id(item: dict[str, Any], index: int) -> _CoercedValue:
    for key in ("task_id", "id", "uid", "key"):
        value = item.get(key)
        if value is not None and str(value).strip():
            return _CoercedValue(str(value).strip(), key)
    return _CoercedValue(f"task-{index}", "generated_index")


def _coerce_prompt(item: dict[str, Any]) -> _CoercedValue:
    for key in ("prompt", "question", "input_text", "input", "text"):
        value = item.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            return _CoercedValue(value, key)
        return _CoercedValue(json.dumps(value, ensure_ascii=False), key)
    return _CoercedValue("", "missing")
