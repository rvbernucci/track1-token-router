import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from router.core.contracts import TaskEnvelope
from router.core.local_runner import LocalM1Runner
from router.core.model_client import LocalModelClient
from tests.fake_openai_server import FakeOpenAIServer


class LocalM1Tests(unittest.TestCase):
    def test_local_model_client_posts_openai_compatible_chat_request(self) -> None:
        with FakeOpenAIServer(response_text="plain local answer") as server:
            client = LocalModelClient(base_url=server.url, model="fake-local", max_retries=0)

            response = client.complete(
                [{"role": "user", "content": "What is 2+2?"}],
                temperature=0.2,
                max_tokens=64,
            )

        self.assertEqual(response.text, "plain local answer")
        self.assertEqual(response.usage.total, 7)
        self.assertEqual(server.requests[0]["path"], "/v1/chat/completions")
        self.assertEqual(server.requests[0]["payload"]["model"], "fake-local")

    def test_local_m1_preserves_free_form_answer(self) -> None:
        with FakeOpenAIServer(response_text="4") as server:
            client = LocalModelClient(base_url=server.url, model="fake-local", max_retries=0)
            runner = LocalM1Runner(client)

            result = runner.run(TaskEnvelope(id="t1", input_text="What is 2+2?"))

        self.assertEqual(result.answer, "4")
        self.assertEqual(result.route, "m1_local")
        self.assertEqual(result.remote_tokens.total, 0)
        self.assertEqual(result.metadata["local_tokens"]["total"], 7)

    def test_local_m1_preserves_requested_format(self) -> None:
        expected = '{"answer":4}'
        with FakeOpenAIServer(response_text=expected) as server:
            client = LocalModelClient(base_url=server.url, model="fake-local", max_retries=0)
            runner = LocalM1Runner(client)

            result = runner.run(TaskEnvelope(input_text="Respond JSON only: what is 2+2?"))

        self.assertEqual(result.answer, expected)

    def test_local_m1_accepts_long_prompts(self) -> None:
        long_prompt = "Summarize this: " + ("token " * 1000)
        with FakeOpenAIServer(response_text="short summary") as server:
            client = LocalModelClient(base_url=server.url, model="fake-local", max_retries=0)
            runner = LocalM1Runner(client)

            result = runner.run(TaskEnvelope(input_text=long_prompt))

        messages = server.requests[0]["payload"]["messages"]
        self.assertEqual(result.answer, "short summary")
        self.assertEqual(messages, [{"role": "user", "content": long_prompt}])

    def test_local_m1_returns_controlled_error_on_model_failure(self) -> None:
        with FakeOpenAIServer(status=500) as server:
            client = LocalModelClient(base_url=server.url, model="fake-local", max_retries=0)
            runner = LocalM1Runner(client)

            result = runner.run(TaskEnvelope(id="t1", input_text="Hello"))

        self.assertEqual(result.route, "local_error")
        self.assertIn("Local model unavailable", result.answer)

    def test_cli_local_mode_calls_local_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "run.jsonl"
            env = {
                **os.environ,
                "ROUTER_MODE": "local",
                "LOCAL_MODEL": "fake-local",
                "LOCAL_MAX_RETRIES": "0",
                "ROUTER_LOG_PATH": str(log_path),
            }
            with FakeOpenAIServer(response_text="plain local answer") as server:
                env["LOCAL_BASE_URL"] = server.url
                completed = subprocess.run(
                    [sys.executable, "-m", "router", "ask", "Say hi"],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=env,
                )

            log_record = json.loads(log_path.read_text(encoding="utf-8").strip())

        self.assertEqual(completed.stdout.strip(), "plain local answer")
        self.assertEqual(completed.stderr.strip(), "")
        self.assertEqual(log_record["route"], "m1_local")
        self.assertIn("latency_ms", log_record["extra"])
        self.assertEqual(log_record["extra"]["model_1_candidate_raw"], "plain local answer")


if __name__ == "__main__":
    unittest.main()
