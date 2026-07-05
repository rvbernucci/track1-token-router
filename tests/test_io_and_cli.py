import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from router.adapters.io import load_jsonl_tasks, parse_json_task


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


if __name__ == "__main__":
    unittest.main()

