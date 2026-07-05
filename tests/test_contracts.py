import json
import unittest

from router.core.contracts import AnswerResult, FileAttachment, TaskEnvelope, TokenUsage


class ContractTests(unittest.TestCase):
    def test_task_envelope_round_trip(self) -> None:
        task = TaskEnvelope(
            id="task-1",
            input_text="What is 2+2?",
            files=[FileAttachment(name="note.txt", path="/tmp/note.txt", mime_type="text/plain")],
            metadata={"source": "unit"},
        )

        restored = TaskEnvelope.from_mapping(json.loads(task.to_json()))

        self.assertEqual(restored.id, "task-1")
        self.assertEqual(restored.input_text, "What is 2+2?")
        self.assertEqual(restored.files[0].name, "note.txt")
        self.assertEqual(restored.metadata["source"], "unit")

    def test_task_envelope_accepts_aliases(self) -> None:
        task = TaskEnvelope.from_mapping({"id": 7, "question": "Hello?"})

        self.assertEqual(task.id, "7")
        self.assertEqual(task.input_text, "Hello?")

    def test_answer_result_serializes_token_usage(self) -> None:
        result = AnswerResult(
            id="a",
            answer="ok",
            route="mock_foundation",
            remote_tokens=TokenUsage(prompt=1, completion=2, total=3),
        )

        payload = json.loads(result.to_json())

        self.assertEqual(payload["answer"], "ok")
        self.assertEqual(payload["remote_tokens"]["total"], 3)


if __name__ == "__main__":
    unittest.main()

