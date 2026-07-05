import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from router.core.contracts import AnswerResult, TaskEnvelope
from router.orchestration.state_machine import (
    ORCHESTRATION_EVENTS,
    ORCHESTRATION_STATES,
    OrchestratedRunner,
    build_orchestration_trace,
)


class StateMachineTests(unittest.TestCase):
    def test_canonical_states_and_events_are_defined(self) -> None:
        self.assertIn("received", ORCHESTRATION_STATES)
        self.assertIn("remote_audit", ORCHESTRATION_STATES)
        self.assertIn("failed", ORCHESTRATION_STATES)
        self.assertIn("escalate", ORCHESTRATION_EVENTS)
        self.assertIn("fallback", ORCHESTRATION_EVENTS)

    def test_trace_for_m1_approved_has_final_state(self) -> None:
        task = TaskEnvelope(id="t1", input_text="What is 2+2?")
        result = AnswerResult(id="t1", answer="4", route="m1_approved")
        trace = build_orchestration_trace(task, result)

        self.assertEqual(trace.final_route, "m1_approved")
        self.assertEqual(trace.steps[-1].state, "final")
        self.assertEqual(trace.steps[-1].event, "approve")

    def test_trace_for_remote_parse_failure_records_fallback(self) -> None:
        task = TaskEnvelope(id="t2", input_text="hard")
        result = AnswerResult(
            id="t2",
            answer="raw",
            route="fireworks_replaced",
            metadata={"fireworks_parse_failed": True},
        )
        trace = build_orchestration_trace(task, result)

        self.assertEqual(trace.fallback, "replace_with_remote_raw_text")
        self.assertIn("remote_audit", [step.state for step in trace.steps])
        self.assertEqual(trace.steps[-1].state, "final")

    def test_orchestrated_runner_uses_guardrail_before_inner_runner(self) -> None:
        inner = CountingRunner("inner")
        runner = OrchestratedRunner(inner, enable_guardrails=True)

        result = runner.run(TaskEnvelope(input_text="What is 10 + 5?"))

        self.assertEqual(result.route, "guardrail_arithmetic")
        self.assertEqual(result.answer, "15")
        self.assertEqual(inner.calls, 0)
        self.assertEqual(result.metadata["orchestration_trace"]["steps"][-1]["state"], "final")

    def test_orchestrated_runner_adds_trace_to_delegated_result(self) -> None:
        runner = OrchestratedRunner(CountingRunner("m2b_candidate"), enable_guardrails=False)

        result = runner.run(TaskEnvelope(id="x", input_text="Explain Nash."))

        self.assertEqual(result.route, "m2b_candidate")
        self.assertIn("orchestration_trace", result.metadata)
        self.assertEqual(result.metadata["orchestration_trace"]["final_route"], "m2b_candidate")

    def test_cli_can_enable_orchestrator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["ENABLE_ORCHESTRATOR"] = "1"
            env["ENABLE_GUARDRAILS"] = "1"
            env["ROUTER_LOG_PATH"] = str(Path(tmp) / "run.jsonl")
            completed = subprocess.run(
                [sys.executable, "-m", "router", "ask", "What is 10 + 5?", "--json"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["route"], "guardrail_arithmetic")
        self.assertIn("orchestration_trace", payload["metadata"])

    def test_orchestrator_repairs_strict_format_when_possible(self) -> None:
        runner = OrchestratedRunner(CountingRunner("mock_foundation"), enable_guardrails=False)

        result = runner.run(TaskEnvelope(input_text="Return exactly SAFE_OUTPUT and nothing else."))

        self.assertEqual(result.answer, "SAFE_OUTPUT")
        self.assertTrue(result.metadata["final_answer_repaired"])


class CountingRunner:
    def __init__(self, route: str) -> None:
        self.route = route
        self.calls = 0

    def run(self, task: TaskEnvelope) -> AnswerResult:
        self.calls += 1
        return AnswerResult(id=task.id, answer="delegated", route=self.route)


if __name__ == "__main__":
    unittest.main()
