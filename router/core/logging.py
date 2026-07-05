from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from router.core.contracts import AnswerResult, TaskEnvelope


class JsonlRunLogger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def log_result(self, task: TaskEnvelope, result: AnswerResult, extra: dict[str, Any] | None = None) -> None:
        record: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "task_id": task.id,
            "input_sha256": _sha256(task.input_text),
            "route": result.route,
            "remote_tokens": result.remote_tokens.to_dict(),
            "answer_chars": len(result.answer),
        }
        if extra:
            record["extra"] = extra
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

