import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from router.core.contracts import TaskEnvelope
from router.core.local_cascade import LocalCascadeRunner
from router.core.model_client import LocalModelClient
from router.core.verifier import parse_verification_decision
from tests.fake_openai_server import FakeOpenAIServer


APPROVE_JSON = json.dumps(
    {
        "decision": "approve",
        "confidence": "high",
        "reason": "simple exact answer",
        "failure_modes": [],
        "should_generate_alternative": False,
    }
)

ESCALATE_JSON = json.dumps(
    {
        "decision": "escalate",
        "confidence": "medium",
        "reason": "candidate has math risk",
        "failure_modes": ["math"],
        "should_generate_alternative": True,
    }
)


class LocalCascadeTests(unittest.TestCase):
    def test_m2a_approval_returns_m1_candidate(self) -> None:
        with FakeOpenAIServer(responses=["4", APPROVE_JSON]) as server:
            client = LocalModelClient(base_url=server.url, model="fake-local", max_retries=0)
            runner = LocalCascadeRunner(client)

            result = runner.run(TaskEnvelope(id="easy", input_text="What is 2+2?"))

        self.assertEqual(result.route, "m1_approved")
        self.assertEqual(result.answer, "4")
        self.assertEqual(len(server.requests), 2)

    def test_m2a_escalation_returns_m2b_free_form_candidate(self) -> None:
        with FakeOpenAIServer(responses=["5", ESCALATE_JSON, "4"]) as server:
            client = LocalModelClient(base_url=server.url, model="fake-local", max_retries=0)
            runner = LocalCascadeRunner(client)

            result = runner.run(TaskEnvelope(id="hard", input_text="What is 2+2?"))

        self.assertEqual(result.route, "m2b_candidate")
        self.assertEqual(result.answer, "4")
        self.assertEqual(len(server.requests), 3)

    def test_invalid_m2a_json_escalates_to_m2b(self) -> None:
        with FakeOpenAIServer(responses=["5", "not-json", "4"]) as server:
            client = LocalModelClient(base_url=server.url, model="fake-local", max_retries=0)
            runner = LocalCascadeRunner(client)

            result = runner.run(TaskEnvelope(id="repair", input_text="What is 2+2?"))

        self.assertEqual(result.route, "m2b_candidate")
        self.assertEqual(result.answer, "4")

    def test_verifier_parser_extracts_json_without_markdown(self) -> None:
        decision = parse_verification_decision(f"```json\n{APPROVE_JSON}\n```")

        self.assertEqual(decision.decision, "approve")
        self.assertEqual(decision.confidence, "high")

    def test_cli_cascade_mode_never_outputs_m2a_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "run.jsonl"
            env = {
                **os.environ,
                "ROUTER_MODE": "cascade",
                "LOCAL_MODEL": "fake-local",
                "LOCAL_MAX_RETRIES": "0",
                "ROUTER_LOG_PATH": str(log_path),
            }
            with FakeOpenAIServer(responses=["5", ESCALATE_JSON, "4"]) as server:
                env["LOCAL_BASE_URL"] = server.url
                completed = subprocess.run(
                    [sys.executable, "-m", "router", "ask", "What is 2+2?"],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=env,
                )

            log_record = json.loads(log_path.read_text(encoding="utf-8").strip())

        self.assertEqual(completed.stdout.strip(), "4")
        self.assertNotIn('"decision"', completed.stdout)
        self.assertEqual(log_record["route"], "m2b_candidate")
        self.assertEqual(log_record["extra"]["m2a_decision"]["decision"], "escalate")
        self.assertEqual(log_record["extra"]["model_2_alternative_raw"], "4")


if __name__ == "__main__":
    unittest.main()

