import json
import os
import subprocess
import sys
import tempfile
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
                "lablab_track1",
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

    def test_lablab_track1_round_trip(self) -> None:
        adapter = get_adapter("lablab_track1")
        tasks = adapter.parse((FIXTURES / "lablab_track1_tasks.json").read_text(encoding="utf-8"))

        output = adapter.format(
            [
                AnswerResult(id=tasks[0].id, answer="Local verification reduces token spend.", route="test"),
                AnswerResult(id=tasks[1].id, answer="42", route="test"),
            ]
        )
        payload = json.loads(output)

        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0].id, "t1")
        self.assertEqual(tasks[0].input_text.startswith("Summarise"), True)
        self.assertEqual(tasks[0].metadata["adapter"], "lablab_track1")
        self.assertEqual(payload[0], {"task_id": "t1", "answer": "Local verification reduces token spend."})
        self.assertEqual(payload[1], {"task_id": "t2", "answer": "42"})

    def test_lablab_track1_accepts_enveloped_tasks_and_alias_fields(self) -> None:
        adapter = get_adapter("lablab_track1")
        raw = json.dumps(
            {
                "run_id": "official-variant",
                "scoring": {"primary": "accuracy"},
                "tasks": [
                    {
                        "id": "alias-1",
                        "question": "What is 2 + 2? Return only the number.",
                        "category": "math",
                        "metadata": {"difficulty": "easy"},
                    },
                    {
                        "uid": "alias-2",
                        "input_text": "Classify sentiment: Text: reliable and clean.",
                        "domain": "sentiment",
                    },
                ],
            }
        )

        tasks = adapter.parse(raw)

        self.assertEqual([task.id for task in tasks], ["alias-1", "alias-2"])
        self.assertEqual(tasks[0].input_text, "What is 2 + 2? Return only the number.")
        self.assertEqual(tasks[0].metadata["input_shape"], "object.tasks")
        self.assertEqual(tasks[0].metadata["source_id_field"], "id")
        self.assertEqual(tasks[0].metadata["source_prompt_field"], "question")
        self.assertEqual(tasks[0].metadata["run_id"], "official-variant")
        self.assertEqual(tasks[0].metadata["category"], "math")
        self.assertEqual(tasks[0].metadata["difficulty"], "easy")
        self.assertEqual(tasks[1].metadata["source_id_field"], "uid")
        self.assertEqual(tasks[1].metadata["source_prompt_field"], "input_text")

    def test_lablab_track1_generates_stable_id_when_missing(self) -> None:
        adapter = get_adapter("lablab_track1")

        tasks = adapter.parse(json.dumps({"items": [{"text": "Hello"}]}))
        output = adapter.format([AnswerResult(id=tasks[0].id, answer="Hi", route="test")])

        self.assertEqual(tasks[0].id, "task-1")
        self.assertEqual(tasks[0].metadata["input_shape"], "object.items")
        self.assertEqual(tasks[0].metadata["source_id_field"], "generated_index")
        self.assertEqual(json.loads(output), [{"task_id": "task-1", "answer": "Hi"}])

    def test_lablab_track1_rejects_object_without_task_list(self) -> None:
        adapter = get_adapter("lablab_track1")

        with self.assertRaisesRegex(ValueError, "requires one list field"):
            adapter.parse(json.dumps({"prompt": "Hello"}))

    def test_lablab_track1_cli_submission_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()
            output_dir.mkdir()
            input_path = input_dir / "tasks.json"
            output_path = output_dir / "results.json"
            input_path.write_text((FIXTURES / "lablab_track1_tasks.json").read_text(encoding="utf-8"), encoding="utf-8")
            env = {
                **os.environ,
                "ROUTER_MODE": "mock",
                "ROUTER_LOG_PATH": str(root / "run.jsonl"),
            }

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "router",
                    "submit-track1",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.stdout, "")
        self.assertEqual([row["task_id"] for row in payload], ["t1", "t2"])
        self.assertTrue(all(isinstance(row["answer"], str) and row["answer"] for row in payload))

    def test_lablab_track1_cli_writes_fallbacks_when_runtime_budget_is_exhausted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "tasks.json"
            output_path = root / "results.json"
            input_path.write_text(
                json.dumps(
                    [
                        {"task_id": "late-1", "prompt": "Summarise this: one."},
                        {"task_id": "late-2", "prompt": "Summarise this: two."},
                    ]
                ),
                encoding="utf-8",
            )
            env = {
                **os.environ,
                "ROUTER_MODE": "mock",
                "TRACK1_MAX_RUNTIME_S": "0",
                "TRACK1_RUNTIME_RESERVE_S": "0",
                "ROUTER_LOG_PATH": str(root / "run.jsonl"),
            }

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "router",
                    "submit-track1",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.stdout, "")
        self.assertEqual([row["task_id"] for row in payload], ["late-1", "late-2"])
        self.assertTrue(all(row["answer"].startswith("Unable to complete") for row in payload))

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
