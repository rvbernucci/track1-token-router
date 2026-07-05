import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from router.core.contracts import AnswerResult, TaskEnvelope, TokenUsage
from router.core.fireworks import FireworksClient
from router.core.hybrid_cascade import HybridCascadeRunner
from router.core.model_client import LocalModelClient
from tests.fake_openai_server import FakeOpenAIServer
from tests.test_local_cascade import APPROVE_JSON, ESCALATE_JSON


FIREWORKS_APPROVE_JSON = json.dumps(
    {
        "decision": "approve",
        "answer": "",
        "reason": "M2B is correct",
    }
)

FIREWORKS_REPLACE_JSON = json.dumps(
    {
        "decision": "replace",
        "answer": "4",
        "reason": "M2B was still wrong",
    }
)


class HybridCascadeTests(unittest.TestCase):
    def test_fireworks_not_called_when_m2a_approves(self) -> None:
        with FakeOpenAIServer(responses=["4", APPROVE_JSON]) as local_server:
            with FakeOpenAIServer(response_text=FIREWORKS_APPROVE_JSON) as fireworks_server:
                runner = _runner(local_server.url, fireworks_server.url)

                result = runner.run(TaskEnvelope(id="easy", input_text="What is 2+2?"))

        self.assertEqual(result.route, "m1_approved")
        self.assertEqual(result.answer, "4")
        self.assertEqual(result.remote_tokens.total, 0)
        self.assertEqual(len(fireworks_server.requests), 0)

    def test_fireworks_approves_m2b_candidate_after_escalation(self) -> None:
        with FakeOpenAIServer(responses=["5", ESCALATE_JSON, "4"]) as local_server:
            with FakeOpenAIServer(response_text=FIREWORKS_APPROVE_JSON) as fireworks_server:
                runner = _runner(local_server.url, fireworks_server.url)

                result = runner.run(TaskEnvelope(id="repair", input_text="What is 2+2?"))

        self.assertEqual(result.route, "m2b_fireworks_approved")
        self.assertEqual(result.answer, "4")
        self.assertEqual(result.remote_tokens.total, 7)
        self.assertEqual(len(fireworks_server.requests), 1)

    def test_fireworks_replaces_bad_m2b_candidate(self) -> None:
        with FakeOpenAIServer(responses=["5", ESCALATE_JSON, "still wrong"]) as local_server:
            with FakeOpenAIServer(response_text=FIREWORKS_REPLACE_JSON) as fireworks_server:
                runner = _runner(local_server.url, fireworks_server.url)

                result = runner.run(TaskEnvelope(id="replace", input_text="What is 2+2?"))

        self.assertEqual(result.route, "fireworks_replaced")
        self.assertEqual(result.answer, "4")
        self.assertEqual(result.remote_tokens.total, 7)
        self.assertFalse(result.metadata["fireworks_parse_failed"])

    def test_cli_hybrid_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "run.jsonl"
            env = {
                **os.environ,
                "ROUTER_MODE": "hybrid",
                "LOCAL_MODEL": "fake-local",
                "LOCAL_MAX_RETRIES": "0",
                "FIREWORKS_MODEL": "fake-fireworks",
                "FIREWORKS_API_KEY": "test-key",
                "FIREWORKS_MAX_RETRIES": "0",
                "ROUTER_LOG_PATH": str(log_path),
            }
            with FakeOpenAIServer(responses=["5", ESCALATE_JSON, "4"]) as local_server:
                with FakeOpenAIServer(response_text=FIREWORKS_APPROVE_JSON) as fireworks_server:
                    env["LOCAL_BASE_URL"] = local_server.url
                    env["FIREWORKS_BASE_URL"] = fireworks_server.url
                    completed = subprocess.run(
                        [sys.executable, "-m", "router", "ask", "What is 2+2?", "--json"],
                        check=True,
                        capture_output=True,
                        text=True,
                        env=env,
                    )

            payload = json.loads(completed.stdout)
            log_record = json.loads(log_path.read_text(encoding="utf-8").strip())

        self.assertEqual(payload["route"], "m2b_fireworks_approved")
        self.assertEqual(payload["remote_tokens"]["total"], 7)
        self.assertEqual(log_record["extra"]["fireworks_decision"]["decision"], "approve")


def _runner(local_url: str, fireworks_url: str) -> HybridCascadeRunner:
    local_client = LocalModelClient(base_url=local_url, model="fake-local", max_retries=0)
    fireworks_client = FireworksClient(
        base_url=fireworks_url,
        model="fake-fireworks",
        api_key="test-key",
        max_retries=0,
    )
    return HybridCascadeRunner(local_client, fireworks_client)


if __name__ == "__main__":
    unittest.main()

