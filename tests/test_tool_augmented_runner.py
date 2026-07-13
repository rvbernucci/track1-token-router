import json
import unittest

from router.core.contracts import AnswerResult, TaskEnvelope, TokenUsage
from router.core.model_client import ModelClientError, ModelResponse
from router.core.tool_augmented_runner import ToolAugmentedRunner, is_tool_planner_candidate
from router.core.tool_planner import TOOL_PLAN_SCHEMA_VERSION
from router.functiongemma.tool_planner_provider import FunctionGemmaToolPlannerProvider


class Fallback:
    def run(self, task):
        return AnswerResult(id=task.id, answer="remote", route="fireworks", remote_tokens=TokenUsage(total=10))


class Client:
    model = "gemma4-e2b"

    def __init__(self, text="", error=None):
        self.text = text
        self.error = error
        self.calls = 0

    def complete(self, messages, *, temperature, max_tokens, extra_body=None):
        self.calls += 1
        if self.error:
            raise self.error
        return ModelResponse(self.text, TokenUsage(prompt=20, completion=30, total=50))


def plan(tool, arguments, confidence="high"):
    return json.dumps({
        "schema_version": TOOL_PLAN_SCHEMA_VERSION,
        "tool": tool, "arguments": arguments, "confidence": confidence,
    })


class ToolAugmentedRunnerTests(unittest.TestCase):
    def test_candidate_prefilter_is_narrow(self):
        self.assertTrue(is_tool_planner_candidate("Evaluate (24 + 12) / 6."))
        self.assertTrue(is_tool_planner_candidate("A recipe uses 1/2 cup for 4 servings. Find cost for 8 at $2 per cup."))
        self.assertFalse(is_tool_planner_candidate("Who is the president of France?"))
        self.assertFalse(is_tool_planner_candidate("Write Python code for 2 + 2."))

    def test_verified_plan_releases_zero_remote_tokens(self):
        raw = plan("safe_calculator", {"ast": {
            "op": "add", "left": {"op": "literal", "value": 2}, "right": {"op": "literal", "value": 3},
        }})
        client = Client(raw)
        runner = ToolAugmentedRunner(planner_client=client, fallback_runner=Fallback(), enabled=True)
        result = runner.run(TaskEnvelope(id="t", input_text="Calculate 2 + 3. Return only the number."))
        self.assertEqual(result.answer, "5")
        self.assertEqual(result.route, "functiongemma_tool_verified")
        self.assertEqual(result.remote_tokens.total, 0)
        self.assertEqual(client.calls, 1)

    def test_disabled_prefilter_deadline_bad_plan_and_error_fall_back(self):
        task = TaskEnvelope(id="t", input_text="Calculate 2 + 3.")
        cases = (
            (ToolAugmentedRunner(planner_client=Client(), fallback_runner=Fallback()), task, None, "policy_disabled"),
            (ToolAugmentedRunner(planner_client=Client(), fallback_runner=Fallback(), enabled=True), TaskEnvelope(id="t", input_text="Explain rain."), None, "structural_prefilter_rejected"),
            (ToolAugmentedRunner(planner_client=Client(), fallback_runner=Fallback(), enabled=True), task, 1, "deadline_guard"),
            (ToolAugmentedRunner(planner_client=Client("invalid"), fallback_runner=Fallback(), enabled=True), task, None, "tool_route_rejected:ValueError"),
            (ToolAugmentedRunner(planner_client=Client(error=ModelClientError("down")), fallback_runner=Fallback(), enabled=True), task, None, "planner_failure:ModelClientError"),
        )
        for runner, current_task, remaining, reason in cases:
            with self.subTest(reason=reason):
                result = runner.run(current_task, remaining_ms=remaining)
                self.assertEqual(result.route, "fireworks")
                self.assertEqual(result.metadata["tool_route"]["reason"], reason)

    def test_model_cannot_release_python_or_hallucinated_number(self):
        prompts = (
            ("Calculate 2 + 3.", plan("safe_calculator", {"ast": {"op": "literal", "value": 9}})),
            ("Write Python code for 2 + 3.", '{"schema_version":"tool-plan-v2","tool":"python_candidate","arguments":{},"confidence":"high"}'),
        )
        for prompt, raw in prompts:
            runner = ToolAugmentedRunner(planner_client=Client(raw), fallback_runner=Fallback(), enabled=True)
            result = runner.run(TaskEnvelope(id="t", input_text=prompt))
            self.assertEqual(result.route, "fireworks")

    def test_native_functiongemma_plan_uses_the_same_proof_pipeline(self):
        response = {"choices": [{"message": {"tool_calls": [{"function": {
            "name": "safe_calculator",
            "arguments": {"ast": {
                "op": "add", "left": {"op": "literal", "value": 2},
                "right": {"op": "literal", "value": 3},
            }},
        }}]}}]}
        provider = FunctionGemmaToolPlannerProvider(
            base_url="http://planner/v1", model="functiongemma-planner",
            requester=lambda _: response,
        )
        runner = ToolAugmentedRunner(
            planner_provider=provider, fallback_runner=Fallback(), enabled=True,
        )
        result = runner.run(TaskEnvelope(id="t", input_text="Calculate 2 + 3. Return only the number."))
        self.assertEqual(result.answer, "5")
        self.assertEqual(result.route, "functiongemma_tool_verified")
        self.assertEqual(result.metadata["planner_model"], "functiongemma-planner")
        self.assertEqual(result.remote_tokens.total, 0)


if __name__ == "__main__":
    unittest.main()
