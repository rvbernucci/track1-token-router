import unittest

from router.core.contracts import AnswerResult, TaskEnvelope, TokenUsage
from router.core.fireworks_verify_repair import (
    FireworksVerifyRepairRunner, build_verify_repair_messages, parse_verify_repair,
)
from router.core.model_client import ModelResponse


class Client:
    model = "allowed-model"

    def __init__(self, text: str):
        self.text = text
        self.calls = 0

    def complete(self, messages, **kwargs):
        self.calls += 1
        self.messages = messages
        return ModelResponse(self.text, TokenUsage(10, 4, 14))


class Fallback:
    def __init__(self):
        self.calls = 0

    def run(self, task):
        self.calls += 1
        return AnswerResult(answer="remote", route="fireworks_direct", id=task.id, remote_tokens=TokenUsage(8, 2, 10))


class VerifyRepairTests(unittest.TestCase):
    def test_prompt_contains_no_official_json_envelope(self) -> None:
        messages = build_verify_repair_messages("Question?", "Candidate")
        self.assertIn("Question?", messages[1]["content"])
        self.assertNotIn("task_id", messages[1]["content"])

    def test_approval_releases_candidate_in_one_call(self) -> None:
        client, fallback = Client("APPROVE"), Fallback()
        runner = FireworksVerifyRepairRunner(client, fallback_runner=fallback)
        result = runner.run(TaskEnvelope(id="t", input_text="Say yes or no."), AnswerResult(answer="yes", route="e2b", id="t"))
        self.assertEqual(result.answer, "yes")
        self.assertEqual(client.calls, 1)
        self.assertEqual(fallback.calls, 0)

    def test_rejection_releases_replacement_without_second_call(self) -> None:
        client, fallback = Client("REPLACE\nno"), Fallback()
        runner = FireworksVerifyRepairRunner(client, fallback_runner=fallback)
        result = runner.run(TaskEnvelope(id="t", input_text="Say yes or no."), AnswerResult(answer="yes", route="e2b", id="t"))
        self.assertEqual(result.answer, "no")
        self.assertEqual(client.calls, 1)
        self.assertEqual(fallback.calls, 0)

    def test_malformed_output_fails_closed_to_direct(self) -> None:
        client, fallback = Client("not json"), Fallback()
        result = FireworksVerifyRepairRunner(client, fallback_runner=fallback).run(
            TaskEnvelope(id="t", input_text="Question"), AnswerResult(answer="candidate", route="e2b", id="t"),
        )
        self.assertEqual(result.answer, "remote")
        self.assertEqual(client.calls, 1)
        self.assertEqual(fallback.calls, 1)

    def test_parser_rejects_extra_control_text(self) -> None:
        with self.assertRaises(ValueError):
            parse_verify_repair("APPROVE because it is correct")


if __name__ == "__main__":
    unittest.main()
