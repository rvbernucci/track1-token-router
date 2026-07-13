import json
import unittest

from router.core.contracts import TaskEnvelope
from router.functiongemma.tool_planner_provider import (
    FunctionGemmaToolPlannerError,
    FunctionGemmaToolPlannerProvider,
)


class FunctionGemmaToolPlannerProviderTests(unittest.TestCase):
    def test_openai_tool_call_is_parsed_and_request_is_bounded(self):
        observed = {}

        def requester(payload):
            observed.update(payload)
            return {
                "choices": [{"message": {"tool_calls": [{"function": {
                    "name": "safe_calculator",
                    "arguments": json.dumps({"ast": {"op": "literal", "value": 4}}),
                }}]}}],
                "usage": {"prompt_tokens": 30, "completion_tokens": 12, "total_tokens": 42},
            }

        provider = FunctionGemmaToolPlannerProvider(base_url="http://local/v1", model="planner", requester=requester)
        invocation = provider.plan_with_trace(TaskEnvelope(id="t", input_text="Calculate 4."))
        self.assertEqual(invocation.plan.tool, "safe_calculator")
        self.assertEqual(invocation.usage.total, 42)
        self.assertEqual(observed["tool_choice"], "required")
        self.assertEqual(observed["max_tokens"], 160)
        self.assertEqual(len(observed["tools"]), 5)

    def test_native_decline_is_fail_closed(self):
        response = {"choices": [{"message": {"content": (
            "<start_function_call>call:decline_tool{reason:<escape>unsupported<escape>}"
            "<end_function_call>"
        )}}]}
        provider = FunctionGemmaToolPlannerProvider(
            base_url="http://local/v1", model="planner", requester=lambda _: response,
        )
        invocation = provider.plan_with_trace(TaskEnvelope(id="t", input_text="Explain rain."))
        self.assertEqual(invocation.plan.tool, "none")

    def test_malformed_or_unknown_call_raises_provider_error(self):
        response = {"choices": [{"message": {"tool_calls": [{"function": {
            "name": "run_python", "arguments": {},
        }}]}}]}
        provider = FunctionGemmaToolPlannerProvider(
            base_url="http://local/v1", model="planner", requester=lambda _: response,
        )
        with self.assertRaises(FunctionGemmaToolPlannerError):
            provider.plan_with_trace(TaskEnvelope(id="t", input_text="Run Python."))


if __name__ == "__main__":
    unittest.main()
