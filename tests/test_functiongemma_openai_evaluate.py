from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.functiongemma_openai_evaluate import assessment_from_openai_response, evaluate
from router.core.contracts import TaskAssessment
from router.functiongemma.tooling import training_conversation


ARGUMENTS = {
    "intent": "math_reasoning",
    "scores": {
        "deterministic_fit": 8,
        "reasoning_demand": 2,
        "knowledge_uncertainty": 0,
        "generation_demand": 2,
        "format_complexity": 2,
    },
}


class FunctionGemmaOpenAIEvaluationTests(unittest.TestCase):
    def test_parses_structured_tool_call(self) -> None:
        payload = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {"function": {"name": "assess_task", "arguments": ARGUMENTS}}
                        ]
                    }
                }
            ]
        }
        self.assertEqual(assessment_from_openai_response(payload).to_dict(), ARGUMENTS)

    def test_parses_json_encoded_tool_arguments(self) -> None:
        import json

        payload = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {"function": {"name": "assess_task", "arguments": json.dumps(ARGUMENTS)}}
                        ]
                    }
                }
            ]
        }
        self.assertEqual(assessment_from_openai_response(payload).to_dict(), ARGUMENTS)

    def test_rejects_extra_choices_and_unknown_tools(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one choice"):
            assessment_from_openai_response({"choices": []})
        with self.assertRaisesRegex(ValueError, "unexpected function"):
            assessment_from_openai_response(
                {
                    "choices": [
                        {"message": {"tool_calls": [{"function": {"name": "route", "arguments": {}}}]}}
                    ]
                }
            )

    def test_accepts_native_call_when_server_strips_the_stop_delimiter(self) -> None:
        content = (
            "<start_function_call>call:assess_task{"
            "intent:<escape>math_reasoning<escape>,scores:{"
            "deterministic_fit:8,reasoning_demand:2,knowledge_uncertainty:0,"
            "generation_demand:2,format_complexity:2}}"
        )
        result = assessment_from_openai_response({"choices": [{"message": {"content": content}}]})
        self.assertEqual(result.to_dict(), ARGUMENTS)

    def test_rejects_native_call_with_trailing_text(self) -> None:
        content = (
            "<start_function_call>call:assess_task{"
            "intent:<escape>math_reasoning<escape>,scores:{"
            "deterministic_fit:8,reasoning_demand:2,knowledge_uncertainty:0,"
            "generation_demand:2,format_complexity:2}}<end_function_call>extra"
        )
        with self.assertRaisesRegex(ValueError, "additional text"):
            assessment_from_openai_response({"choices": [{"message": {"content": content}}]})

    def test_resume_skips_fsynced_existing_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks.jsonl"
            output = root / "predictions.jsonl"
            report = root / "report.json"
            assessment = TaskAssessment.from_mapping(ARGUMENTS)
            rows = []
            for task_id in ("a", "b"):
                row = {"id": task_id, **training_conversation("Compute 2+2.", assessment)}
                rows.append(row)
            tasks.write_text("".join(json.dumps(row) + "\n" for row in rows))
            response = {"choices": [{"message": {"tool_calls": [{"function": {"name": "assess_task", "arguments": ARGUMENTS}}]}}]}
            with patch("scripts.functiongemma_openai_evaluate.request_assessment", return_value=response) as request:
                evaluate(
                    base_url="http://unused/v1", model="test", tasks_path=tasks,
                    output=output, report_path=report, max_tokens=64, timeout_s=1, resume=True,
                )
                first_calls = request.call_count
                second = evaluate(
                    base_url="http://unused/v1", model="test", tasks_path=tasks,
                    output=output, report_path=report, max_tokens=64, timeout_s=1, resume=True,
                )
        self.assertEqual(first_calls, 2)
        self.assertEqual(second["already_complete"], 2)
        self.assertEqual(second["written"], 0)


if __name__ == "__main__":
    unittest.main()
