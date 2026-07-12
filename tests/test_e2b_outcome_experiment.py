import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from router.core.e2b_runner import E2B_SYSTEM_PROMPT
from scripts.e2b_outcome_experiment import _assessment_index, _candidate_id, _complete, _task, run_experiment


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self.payload).encode()


class E2BOutcomeExperimentTests(unittest.TestCase):
    def test_task_supports_envelope_and_training_conversation(self) -> None:
        self.assertEqual(_task({"id": "a", "input_text": " hello "}), ("a", "hello"))
        self.assertEqual(
            _task({"id": "b", "messages": [{"role": "user", "content": "question"}]}),
            ("b", "question"),
        )

    def test_assessment_index_ignores_invalid_predictions_and_rejects_duplicates(self) -> None:
        self.assertEqual(_assessment_index([{"id": "a", "prediction": None}]), {})
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            _assessment_index([{"id": "a", "prediction": {}}, {"id": "a", "prediction": {}}])

    @patch("urllib.request.urlopen")
    def test_complete_records_local_usage_and_zero_fireworks_tokens(self, urlopen) -> None:
        urlopen.return_value = _Response(
            {
                "choices": [{"message": {"content": " 42 "}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 1},
            }
        )
        row = _complete(
            task_id="a",
            task_text="question",
            assessment={"intent": "factual_qa", "scores": {}},
            base_url="http://localhost/v1",
            model="e2b",
            max_tokens=16,
            timeout_s=1,
        )
        self.assertEqual(row["answer"], "42")
        self.assertEqual(row["task_id"], "a")
        self.assertEqual(row["id"], _candidate_id("a", "e2b", 16))
        self.assertEqual(row["generation_limit_tokens"], 16)
        self.assertEqual(row["runtime_id"], "legacy")
        self.assertFalse(row["failure"])
        self.assertEqual(row["local_tokens"], {"prompt": 7, "completion": 1})
        self.assertEqual(row["fireworks_tokens"], {"prompt": 0, "completion": 0})
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["max_completion_tokens"], 16)
        self.assertEqual(payload["max_tokens"], 16)
        self.assertEqual(
            payload["messages"],
            [
                {"role": "system", "content": E2B_SYSTEM_PROMPT},
                {"role": "user", "content": "question"},
            ],
        )
        self.assertEqual(row["prompt_version"], "generic-answer-contract-v1")

    @patch("urllib.request.urlopen")
    def test_run_is_append_only_and_resumable(self, urlopen) -> None:
        urlopen.return_value = _Response({"choices": [{"message": {"content": "ok"}}]})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks.jsonl"
            assessments = root / "assessments.jsonl"
            output = root / "out.jsonl"
            tasks.write_text(json.dumps({"id": "a", "input_text": "question"}) + "\n", encoding="utf-8")
            assessments.write_text(
                json.dumps({"id": "a", "prediction": {"intent": "factual_qa", "scores": {}}}) + "\n",
                encoding="utf-8",
            )
            first = run_experiment(
                tasks_path=tasks,
                assessments_path=assessments,
                output=output,
                base_url="http://localhost/v1",
                model="e2b",
                max_tokens=16,
                timeout_s=1,
            )
            second = run_experiment(
                tasks_path=tasks,
                assessments_path=assessments,
                output=output,
                base_url="http://localhost/v1",
                model="e2b",
                max_tokens=16,
                timeout_s=1,
            )
        self.assertEqual(first["written"], 1)
        self.assertEqual(second["written"], 0)


if __name__ == "__main__":
    unittest.main()
