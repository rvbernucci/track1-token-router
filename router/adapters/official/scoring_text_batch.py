from __future__ import annotations

import re

from router.core.contracts import AnswerResult, TaskEnvelope


TASK_HEADER = re.compile(r"^--- task: (?P<id>.+?) ---$", re.MULTILINE)


class ScoringTextBatchAdapter:
    name = "scoring_text_batch"

    def parse(self, raw: str) -> list[TaskEnvelope]:
        matches = list(TASK_HEADER.finditer(raw))
        if not matches:
            raise ValueError("scoring_text_batch adapter expects task headers.")

        tasks: list[TaskEnvelope] = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
            input_text = raw[start:end].strip()
            if not input_text:
                raise ValueError(f"scoring_text_batch task {match.group('id')} is empty.")
            tasks.append(
                TaskEnvelope(
                    id=match.group("id").strip(),
                    input_text=input_text,
                    metadata={"adapter": self.name},
                )
            )
        return tasks

    def format(self, results: list[AnswerResult]) -> str:
        return "\n".join(f"{result.id or index}\t{result.answer}" for index, result in enumerate(results, start=1))
