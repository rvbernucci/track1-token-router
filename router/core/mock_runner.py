from __future__ import annotations

from router.core.contracts import AnswerResult, TaskEnvelope
from router.core.logging import JsonlRunLogger


class MockCascadeRunner:
    """Sprint 01 runner: proves IO, contracts and logs before model calls exist."""

    def __init__(self, logger: JsonlRunLogger | None = None) -> None:
        self.logger = logger

    def run(self, task: TaskEnvelope) -> AnswerResult:
        answer = _mock_answer(task.input_text)
        result = AnswerResult(
            id=task.id,
            answer=answer,
            route="mock_foundation",
            metadata={"runner": "mock"},
        )
        if self.logger:
            self.logger.log_result(task, result, extra={"stage": "sprint_01"})
        return result


def _mock_answer(input_text: str) -> str:
    stripped = input_text.strip()
    if not stripped:
        return "No task provided."
    if stripped.lower() in {"what is 2+2?", "2+2", "what is 2 + 2?", "2 + 2"}:
        return "4"
    return f"[mock] {stripped}"

