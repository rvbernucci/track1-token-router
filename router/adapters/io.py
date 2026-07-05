from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, TextIO

from router.core.contracts import AnswerResult, TaskEnvelope


def task_from_text(text: str, *, task_id: str | None = None) -> TaskEnvelope:
    return TaskEnvelope(id=task_id, input_text=text)


def parse_json_task(raw: str) -> TaskEnvelope:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("JSON task must be an object.")
    return TaskEnvelope.from_mapping(payload)


def load_jsonl_tasks(path: Path) -> list[TaskEnvelope]:
    tasks: list[TaskEnvelope] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"JSONL line {line_number} must be an object.")
            tasks.append(TaskEnvelope.from_mapping(payload))
    return tasks


def write_jsonl_results(results: Iterable[AnswerResult], handle: TextIO) -> None:
    for result in results:
        handle.write(result.to_json() + "\n")

