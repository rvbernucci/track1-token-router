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
            {
                "plain_text",
                "json_task",
                "jsonl_batch",
                "file_payload",
                "scoring_text_batch",
                "scoring_json_envelope",
                "scoring_file_bundle",
            },
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

    def test_scoring_text_batch_round_trip(self) -> None:
        adapter = get_adapter("scoring_text_batch")
        tasks = adapter.parse(Path("fixtures/adapter-drill/scoring_text_batch.txt").read_text(encoding="utf-8"))

        output = adapter.format(
            [
                AnswerResult(id=task.id, answer=f"DRILL_OK:{task.id}", route="test")
                for task in tasks
            ]
        )

        self.assertEqual(len(tasks), 3)
        self.assertEqual(tasks[0].id, "text-batch-1")
        self.assertEqual(len(output.splitlines()), 3)
        self.assertIn("text-batch-2\tDRILL_OK:text-batch-2", output)

    def test_scoring_json_envelope_round_trip(self) -> None:
        adapter = get_adapter("scoring_json_envelope")
        tasks = adapter.parse(Path("fixtures/adapter-drill/scoring_json_envelope.json").read_text(encoding="utf-8"))

        output = adapter.format(
            [
                AnswerResult(id=tasks[0].id, answer="81", route="test"),
                AnswerResult(id=tasks[1].id, answer='{"ok":true,"count":2}', route="test"),
            ]
        )
        payload = json.loads(output)

        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0].id, "json-envelope-1")
        self.assertEqual(tasks[0].metadata["scoring"]["primary"], "accuracy")
        self.assertEqual(payload["answers"][0]["answer"], "81")

    def test_scoring_file_bundle_round_trip(self) -> None:
        adapter = get_adapter("scoring_file_bundle")
        tasks = adapter.parse(Path("fixtures/adapter-drill/scoring_file_bundle.json").read_text(encoding="utf-8"))

        output = adapter.format([AnswerResult(id=tasks[0].id, answer="short summary", route="test")])

        self.assertEqual(tasks[0].id, "adapter-drill-file-bundle")
        self.assertEqual(tasks[0].files[0].name, "brief.txt")
        self.assertIn("remote token usage", tasks[0].metadata["inline_files"][0]["content"])
        self.assertEqual(output, "short summary")

    def test_unknown_adapter_fails(self) -> None:
        with self.assertRaises(ValueError):
            get_adapter("official-mystery")

    def test_core_does_not_import_official_adapters(self) -> None:
        for path in Path("router/core").glob("*.py"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("router.adapters.official", content, path.name)


if __name__ == "__main__":
    unittest.main()
