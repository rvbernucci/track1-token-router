import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

from router.core.model_client import LocalModelClient, ModelClientError
from tests.fake_openai_server import FakeOpenAIServer


class FakeProviderTests(unittest.TestCase):
    def test_healthcheck(self) -> None:
        with FakeOpenAIServer() as server:
            with urllib.request.urlopen(server.url + "/health", timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["status"], "ok")

    def test_usage_tokens_are_configurable(self) -> None:
        with FakeOpenAIServer(response_text="ok", prompt_tokens=100, completion_tokens=25) as server:
            client = LocalModelClient(base_url=server.url, model="fake", max_retries=0)

            response = client.complete(
                [{"role": "user", "content": "hello"}],
                temperature=0.0,
                max_tokens=16,
            )

        self.assertEqual(response.text, "ok")
        self.assertEqual(response.usage.prompt, 100)
        self.assertEqual(response.usage.completion, 25)
        self.assertEqual(response.usage.total, 125)

    def test_client_merges_extra_body_into_chat_payload(self) -> None:
        with FakeOpenAIServer(response_text="ok") as server:
            client = LocalModelClient(base_url=server.url, model="fake", max_retries=0)

            client.complete(
                [{"role": "user", "content": "hello"}],
                temperature=0.0,
                max_tokens=16,
                extra_body={"reasoning_effort": "none"},
            )

        self.assertEqual(server.requests[0]["payload"]["reasoning_effort"], "none")

    def test_invalid_json_profile_is_controlled(self) -> None:
        with FakeOpenAIServer(invalid_json=True) as server:
            client = LocalModelClient(base_url=server.url, model="fake", max_retries=0)

            with self.assertRaises(ModelClientError):
                client.complete(
                    [{"role": "user", "content": "hello"}],
                    temperature=0.0,
                    max_tokens=16,
                )

    def test_http_error_preserves_sanitized_response_body(self) -> None:
        with FakeOpenAIServer(status=403) as server:
            client = LocalModelClient(base_url=server.url, model="fake", max_retries=0)

            with self.assertRaises(ModelClientError) as raised:
                client.complete(
                    [{"role": "user", "content": "hello"}],
                    temperature=0.0,
                    max_tokens=16,
                )

        message = str(raised.exception)
        self.assertIn("HTTP 403", message)
        self.assertIn("forced failure", message)

    def test_fake_provider_cli_help(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "router.dev.fake_provider", "--help"],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("Run a fake OpenAI-compatible provider", completed.stdout)

    def test_cli_local_timeout_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "run.jsonl"
            env = {
                **os.environ,
                "ROUTER_MODE": "local",
                "LOCAL_MODEL": "fake-local",
                "LOCAL_TIMEOUT_S": "0.01",
                "LOCAL_MAX_RETRIES": "0",
                "ROUTER_LOG_PATH": str(log_path),
            }
            with FakeOpenAIServer(delay_s=0.2) as server:
                env["LOCAL_BASE_URL"] = server.url
                completed = subprocess.run(
                    [sys.executable, "-m", "router", "ask", "slow task", "--json"],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=env,
                )

            payload = json.loads(completed.stdout)

        self.assertEqual(payload["route"], "local_error")
        self.assertIn("Local model unavailable", payload["answer"])


if __name__ == "__main__":
    unittest.main()
