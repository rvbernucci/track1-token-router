import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from router.core.contracts import AnswerResult, TaskEnvelope
from router.orchestration.competition import CompetitionRunner


class CompetitionModeTests(unittest.TestCase):
    def test_guardrail_runs_before_inner_runner(self) -> None:
        inner = CountingRunner(answer="should not run")
        runner = CompetitionRunner(inner, dry_run=True)

        result = runner.run(TaskEnvelope(input_text="What is 10 + 5? Return only the number."))

        self.assertEqual(inner.calls, 0)
        self.assertEqual(result.answer, "15")
        self.assertEqual(result.route, "guardrail_arithmetic")
        trace = result.metadata["competition_trace"]
        self.assertEqual(trace["decision"]["action"], "approve")
        self.assertIn("policy_decision", trace["decision"])
        self.assertIn("budget_decision", trace["decision"])
        self.assertIn("final_validation", trace["decision"])

    def test_final_validator_repairs_safe_strict_format(self) -> None:
        runner = CompetitionRunner(CountingRunner(answer="The answer is 4"), dry_run=True)

        result = runner.run(TaskEnvelope(input_text="Return only the number: what is 2 + 2"))

        self.assertEqual(result.answer, "4")
        self.assertTrue(result.metadata["final_answer_repaired"])
        self.assertTrue(result.metadata["competition_trace"]["decision"]["final_answer_repaired"])

    def test_remote_audit_is_dry_run_and_records_packet_tokens(self) -> None:
        runner = CompetitionRunner(CountingRunner(answer="I would check the latest source."), dry_run=True)

        result = runner.run(TaskEnvelope(input_text="Who is the CEO of AMD today?"))

        decision = result.metadata["competition_trace"]["decision"]
        self.assertEqual(decision["action"], "remote_audit")
        self.assertTrue(decision["remote_would_call"])
        self.assertTrue(decision["dry_run"])
        self.assertGreater(decision["remote_packet_tokens"], 0)
        self.assertEqual(result.remote_tokens.total, 0)

    def test_cli_ask_competition_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = _competition_env(tmp)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "router",
                    "ask",
                    "What is 10 + 5? Return only the number.",
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["answer"], "15")
        self.assertEqual(payload["route"], "guardrail_arithmetic")
        self.assertIn("competition_trace", payload["metadata"])

    def test_cli_ask_competition_stdout_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = _competition_env(tmp)
            completed = subprocess.run(
                [sys.executable, "-m", "router", "ask", "What is 10 + 5? Return only the number."],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

        self.assertEqual(completed.stdout.strip(), "15")
        self.assertEqual(completed.stderr.strip(), "")

    def test_cli_run_competition_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            tasks = tmp_path / "tasks.jsonl"
            out = tmp_path / "out.jsonl"
            tasks.write_text(
                '{"id":"one","input_text":"What is 10 + 5? Return only the number."}\n',
                encoding="utf-8",
            )

            completed = subprocess.run(
                [sys.executable, "-m", "router", "run", "--jsonl", str(tasks), "--out", str(out)],
                check=True,
                capture_output=True,
                text=True,
                env=_competition_env(tmp),
            )

            payload = json.loads(out.read_text(encoding="utf-8").strip())

        self.assertEqual(payload["id"], "one")
        self.assertEqual(payload["answer"], "15")
        self.assertIn("competition_trace", payload["metadata"])
        self.assertEqual(completed.stdout.strip(), "")


class CountingRunner:
    def __init__(self, answer: str, route: str = "mock_foundation") -> None:
        self.answer = answer
        self.route = route
        self.calls = 0

    def run(self, task: TaskEnvelope) -> AnswerResult:
        self.calls += 1
        return AnswerResult(id=task.id, answer=self.answer, route=self.route)


def _competition_env(tmp: str) -> dict[str, str]:
    env = os.environ.copy()
    env["ROUTER_MODE"] = "competition"
    env["COMPETITION_DRY_RUN"] = "1"
    env["ROUTER_LOG_PATH"] = str(Path(tmp) / "run.jsonl")
    for key in ("LOCAL_BASE_URL", "LOCAL_MODEL", "FIREWORKS_API_KEY", "FIREWORKS_MODEL"):
        env.pop(key, None)
    return env


if __name__ == "__main__":
    unittest.main()
