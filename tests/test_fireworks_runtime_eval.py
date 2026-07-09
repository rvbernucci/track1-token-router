import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.fake_openai_server import FakeOpenAIServer


class FireworksRuntimeEvalTests(unittest.TestCase):
    def test_runtime_eval_uses_dynamic_completion_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "tasks.jsonl"
            output = root / "runtime-results.jsonl"
            report = root / "runtime-report.md"
            dataset.write_text(
                json.dumps(
                    {
                        "id": "number_vowels",
                        "domain": "math_reasoning",
                        "tier": "medium",
                        "prompt": "Return only the number of vowels in this invented label: rzxby.",
                        "validator": {"type": "number_exact", "expected": 0},
                    },
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            with FakeOpenAIServer(response_text="0", prompt_tokens=11, completion_tokens=1) as server:
                env = {**os.environ, "FIREWORKS_API_KEY": "test-key"}
                completed = subprocess.run(
                    [
                        sys.executable,
                        "scripts/fireworks_runtime_eval.py",
                        "--dataset",
                        str(dataset),
                        "--allowed-models",
                        "fake-fireworks",
                        "--base-url",
                        server.url,
                        "--output-jsonl",
                        str(output),
                        "--report",
                        str(report),
                        "--max-tasks",
                        "1",
                        "--budget-usd",
                        "0.10",
                        "--no-matrix-weights",
                        "--json",
                    ],
                    cwd=Path(__file__).resolve().parents[1],
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                )

            summary = json.loads(completed.stdout)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            report_text = report.read_text(encoding="utf-8")

        self.assertEqual(summary["tasks"], 1)
        self.assertEqual(summary["valid"], 1)
        self.assertEqual(rows[0]["route"], "fireworks_direct")
        self.assertEqual(rows[0]["fireworks_completion_token_policy"]["max_tokens"], 16)
        self.assertEqual(server.requests[0]["payload"]["max_tokens"], 16)
        self.assertTrue(report_text.startswith("# Fireworks Runtime Router Eval"))


if __name__ == "__main__":
    unittest.main()
