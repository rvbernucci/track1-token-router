from __future__ import annotations

from typing import Protocol

from router.core.contracts import AnswerResult, TaskEnvelope


class TaskRunner(Protocol):
    def run(self, task: TaskEnvelope) -> AnswerResult:
        ...

