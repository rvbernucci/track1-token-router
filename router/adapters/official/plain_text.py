from __future__ import annotations

from router.core.contracts import AnswerResult, TaskEnvelope


class PlainTextAdapter:
    name = "plain_text"

    def parse(self, raw: str) -> list[TaskEnvelope]:
        return [TaskEnvelope(input_text=raw)]

    def format(self, results: list[AnswerResult]) -> str:
        return "\n".join(result.answer for result in results)
