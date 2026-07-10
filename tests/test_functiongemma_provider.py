import unittest

from router.core.contracts import TaskEnvelope
from router.functiongemma.calibration import OrdinalCalibration, ScoreCalibrationBundle
from router.functiongemma.provider import FunctionGemmaAssessmentProvider, FunctionGemmaProviderError, assessment_from_openai_response


NATIVE = (
    "<start_function_call>call:assess_task{intent:<escape>sentiment<escape>,"
    "scores:{deterministic_fit:2,format_complexity:2,generation_demand:2,"
    "knowledge_uncertainty:1,reasoning_demand:3}}"
)


def calibration():
    identity = OrdinalCalibration(tuple(float(i) for i in range(11)), False, 0.0, 0.0)
    names = ("deterministic_fit", "reasoning_demand", "knowledge_uncertainty", "generation_demand", "format_complexity")
    return ScoreCalibrationBundle(
        dimensions={name: identity for name in names},
        source_sha256="a" * 64,
        artifact_sha256="b" * 64,
    )


class FunctionGemmaProviderTests(unittest.TestCase):
    def test_accepts_native_call_stopped_before_transport_delimiter(self):
        parsed = assessment_from_openai_response({"choices": [{"message": {"content": NATIVE}}]})
        self.assertEqual(parsed.intent.value, "sentiment")

    def test_provider_sends_required_tool_and_returns_calibrated_assessment(self):
        captured = {}

        def requester(payload):
            captured.update(payload)
            return {
                "choices": [{"message": {"content": NATIVE}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 40, "total_tokens": 50},
            }

        provider = FunctionGemmaAssessmentProvider(
            base_url="http://localhost/v1",
            model="functiongemma",
            calibration=calibration(),
            requester=requester,
        )
        result = provider.assess_with_trace(TaskEnvelope(id="task", input_text="Classify this."))
        self.assertEqual(captured["tool_choice"], "required")
        self.assertEqual(captured["max_tokens"], 64)
        self.assertEqual(result.usage.total, 50)

    def test_malformed_output_fails_closed(self):
        provider = FunctionGemmaAssessmentProvider(
            base_url="http://localhost/v1",
            model="functiongemma",
            calibration=calibration(),
            requester=lambda _payload: {"choices": [{"message": {"content": "not a call"}}]},
        )
        with self.assertRaises(FunctionGemmaProviderError):
            provider.assess(TaskEnvelope(id="task", input_text="Anything"))


if __name__ == "__main__":
    unittest.main()
