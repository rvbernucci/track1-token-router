from __future__ import annotations

from typing import Protocol

from router.core.contracts import AnswerResult, TaskEnvelope


class OfficialAdapter(Protocol):
    name: str

    def parse(self, raw: str) -> list[TaskEnvelope]:
        """Convert official input into core TaskEnvelope objects."""

    def format(self, results: list[AnswerResult]) -> str:
        """Convert core AnswerResult objects back into official output."""
