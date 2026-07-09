import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from router.core.contracts import AnswerResult, TaskEnvelope
from router.core.guardrails import GuardedRunner, evaluate_guardrail


class DeterministicGuardrailTests(unittest.TestCase):
    def test_empty_input_is_handled(self) -> None:
        decision = evaluate_guardrail(TaskEnvelope(input_text="   "))

        self.assertIsNotNone(decision)
        self.assertEqual(decision.route, "guardrail_empty")

    def test_simple_greeting_is_handled(self) -> None:
        decision = evaluate_guardrail(TaskEnvelope(input_text="Hello!"))

        self.assertIsNotNone(decision)
        self.assertEqual(decision.route, "guardrail_greeting")

    def test_safe_add_sub_is_handled(self) -> None:
        decision = evaluate_guardrail(TaskEnvelope(input_text="What is 12 - 5? Return only the number."))

        self.assertIsNotNone(decision)
        self.assertEqual(decision.answer, "7")
        self.assertEqual(decision.route, "guardrail_arithmetic")

    def test_literal_echo_is_handled(self) -> None:
        decision = evaluate_guardrail(TaskEnvelope(input_text="Return exactly SAFE_OUTPUT_01 and nothing else."))

        self.assertIsNotNone(decision)
        self.assertEqual(decision.answer, "SAFE_OUTPUT_01")
        self.assertEqual(decision.route, "guardrail_echo")

    def test_literal_echo_this_string_colon_is_handled(self) -> None:
        decision = evaluate_guardrail(TaskEnvelope(input_text="Return exactly this string and nothing else: ROUTER-OK-19"))

        self.assertIsNotNone(decision)
        self.assertEqual(decision.answer, "ROUTER-OK-19")
        self.assertEqual(decision.route, "guardrail_echo")

    def test_complex_math_is_not_handled(self) -> None:
        decision = evaluate_guardrail(TaskEnvelope(input_text="What is 12 * 5 + 3?"))

        self.assertIsNone(decision)

    def test_guarded_runner_delegates_when_no_rule_matches(self) -> None:
        runner = CountingRunner()
        guarded = GuardedRunner(runner)
        result = guarded.run(TaskEnvelope(input_text="Explain Nash equilibrium."))

        self.assertEqual(result.route, "inner")
        self.assertEqual(runner.calls, 1)

    def test_cli_guardrails_are_optional_by_env_var(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["ENABLE_GUARDRAILS"] = "1"
            env["ROUTER_LOG_PATH"] = str(Path(tmp) / "run.jsonl")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "router",
                    "ask",
                    "What is 12 - 5? Return only the number.",
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["answer"], "7")
        self.assertEqual(payload["route"], "guardrail_arithmetic")


class CountingRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, task: TaskEnvelope) -> AnswerResult:
        self.calls += 1
        return AnswerResult(id=task.id, answer="delegated", route="inner")


if __name__ == "__main__":
    unittest.main()
