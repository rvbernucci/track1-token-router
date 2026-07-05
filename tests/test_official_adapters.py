import json
import unittest
from pathlib import Path

from router.adapters.official import ADAPTERS, get_adapter
from router.core.contracts import AnswerResult


FIXTURES = Path("fixtures/official")


class OfficialAdapterTests(unittest.TestCase):
    def test_registry_contains_templates(self) -> None:
        self.assertEqual(
            set(ADAPTERS),
            {"plain_text", "json_task", "jsonl_batch", "file_payload"},
        )

    def test_plain_text_round_trip(self) -> None:
        adapter = get_adapter("plain_text")
        tasks = adapter.parse((FIXTURES / "plain_text.txt").read_text(encoding="utf-8"))

        output = adapter.format([AnswerResult(id=tasks[0].id, answer="4", route="test")])

        self.assertEqual(tasks[0].input_text.strip(), "What is 2+2?")
        self.assertEqual(output, "4")

    def test_json_task_round_trip(self) -> None:
        adapter = get_adapter("json_task")
        tasks = adapter.parse((FIXTURES / "json_task.json").read_text(encoding="utf-8"))

        output = adapter.format([AnswerResult(id=tasks[0].id, answer="4", route="test")])
        payload = json.loads(output)

        self.assertEqual(tasks[0].id, "json-1")
        self.assertEqual(payload["answer"], "4")

    def test_jsonl_batch_round_trip(self) -> None:
        adapter = get_adapter("jsonl_batch")
        tasks = adapter.parse((FIXTURES / "jsonl_batch.jsonl").read_text(encoding="utf-8"))

        output = adapter.format(
            [
                AnswerResult(id=tasks[0].id, answer="4", route="test"),
                AnswerResult(id=tasks[1].id, answer="SAFE_OUTPUT", route="test"),
            ]
        )
        rows = [json.loads(line) for line in output.splitlines()]

        self.assertEqual(len(tasks), 2)
        self.assertEqual(rows[1]["answer"], "SAFE_OUTPUT")

    def test_file_payload_round_trip(self) -> None:
        adapter = get_adapter("file_payload")
        tasks = adapter.parse((FIXTURES / "file_payload.json").read_text(encoding="utf-8"))

        output = adapter.format([AnswerResult(id=tasks[0].id, answer="summary", route="test")])
        payload = json.loads(output)

        self.assertEqual(tasks[0].files[0].name, "brief.txt")
        self.assertEqual(payload["answer"], "summary")

    def test_unknown_adapter_fails(self) -> None:
        with self.assertRaises(ValueError):
            get_adapter("official-mystery")

    def test_core_does_not_import_official_adapters(self) -> None:
        for path in Path("router/core").glob("*.py"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("router.adapters.official", content, path.name)


if __name__ == "__main__":
    unittest.main()
