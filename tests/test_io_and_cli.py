import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from router.adapters.io import load_jsonl_tasks, parse_json_task
from router.core.model_client import LocalModelClient, ModelClientError
from tests.fake_openai_server import FakeOpenAIServer


class AdapterTests(unittest.TestCase):
    def test_parse_json_task(self) -> None:
        task = parse_json_task('{"id":"1","input_text":"Ping"}')

        self.assertEqual(task.id, "1")
        self.assertEqual(task.input_text, "Ping")

    def test_load_jsonl_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tasks.jsonl"
            path.write_text('{"id":"1","input_text":"A"}\n{"id":"2","question":"B"}\n', encoding="utf-8")

            tasks = load_jsonl_tasks(path)

        self.assertEqual([task.input_text for task in tasks], ["A", "B"])


class CliTests(unittest.TestCase):
    def test_ask_stdout_is_final_answer_only(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "router", "ask", "What is 2+2?"],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.stdout.strip(), "4")
        self.assertEqual(completed.stderr.strip(), "")

    def test_solve_json_outputs_answer_result(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "router", "solve", "--json"],
            input='{"id":"x","input_text":"Hello"}',
            check=True,
            capture_output=True,
            text=True,
        )

        payload = json.loads(completed.stdout)

        self.assertEqual(payload["id"], "x")
        self.assertEqual(payload["route"], "mock_foundation")

    def test_run_jsonl_writes_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tasks = Path(tmp) / "tasks.jsonl"
            out = Path(tmp) / "out.jsonl"
            tasks.write_text('{"id":"1","input_text":"What is 2+2?"}\n', encoding="utf-8")

            subprocess.run(
                [sys.executable, "-m", "router", "run", "--jsonl", str(tasks), "--out", str(out)],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(out.read_text(encoding="utf-8").strip())

        self.assertEqual(payload["answer"], "4")

    def test_solve_invalid_json_returns_controlled_error(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "router", "solve", "--json"],
            input="{not-json",
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout.strip(), "")
        self.assertIn("router error:", completed.stderr)

    def test_ask_missing_file_returns_controlled_error(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "router", "ask", "--file", "/tmp/router-missing-file.txt"],
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout.strip(), "")
        self.assertIn("router error:", completed.stderr)


class TimeoutTests(unittest.TestCase):
    def test_model_client_timeout_is_controlled(self) -> None:
        with FakeOpenAIServer(delay_s=0.2) as server:
            client = LocalModelClient(
                base_url=server.url,
                model="fake-local",
                timeout_s=0.01,
                max_retries=0,
            )

            with self.assertRaises(ModelClientError):
                client.complete(
                    [{"role": "user", "content": "slow"}],
                    temperature=0.0,
                    max_tokens=16,
                )


if __name__ == "__main__":
    unittest.main()
