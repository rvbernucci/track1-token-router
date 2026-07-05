from __future__ import annotations

import json

from router.core.contracts import AnswerResult, FileAttachment, TaskEnvelope


class ScoringFileBundleAdapter:
    name = "scoring_file_bundle"

    def parse(self, raw: str) -> list[TaskEnvelope]:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("scoring_file_bundle adapter expects one JSON object.")

        attachments_payload = payload.get("attachments") or []
        if not isinstance(attachments_payload, list):
            raise ValueError("scoring_file_bundle attachments must be a list.")

        files: list[FileAttachment] = []
        inline_files: list[dict[str, str | None]] = []
        for index, item in enumerate(attachments_payload, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"scoring_file_bundle attachment {index} must be an object.")
            filename = str(item.get("filename") or item.get("name") or f"attachment-{index}.txt")
            mime = item.get("mime") or item.get("mime_type")
            content = item.get("content")
            files.append(FileAttachment(name=filename, path=f"inline://{filename}", mime_type=mime))
            inline_files.append(
                {
                    "name": filename,
                    "mime_type": str(mime) if mime is not None else None,
                    "content": str(content) if content is not None else "",
                }
            )

        question = payload.get("question") or payload.get("prompt") or payload.get("input_text")
        if not isinstance(question, str):
            raise ValueError("scoring_file_bundle requires a question string.")

        return [
            TaskEnvelope(
                id=str(payload.get("bundle_id") or "file-bundle-1"),
                input_text=question,
                files=files,
                metadata={
                    "adapter": self.name,
                    "inline_files": inline_files,
                    "output_contract": payload.get("output_contract", {}),
                },
            )
        ]

    def format(self, results: list[AnswerResult]) -> str:
        if len(results) != 1:
            raise ValueError("scoring_file_bundle adapter expects exactly one result.")
        return results[0].answer
