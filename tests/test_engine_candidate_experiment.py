from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from router.core.contracts import TokenUsage
from router.core.model_client import ModelResponse
from scripts.engine_candidate_experiment import _candidate_id, run_experiment


class _Client:
    def __init__(self) -> None:
        self.calls = 0
        self.max_tokens = []

    def complete(self, *_args, **kwargs) -> ModelResponse:
        self.calls += 1
        self.max_tokens.append(kwargs["max_tokens"])
        return ModelResponse("answer", TokenUsage(prompt=10, completion=2, total=12))


class EngineCandidateExperimentTests(unittest.TestCase):
    def test_fireworks_collection_is_budgeted_append_only_and_resumable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks.jsonl"
            assessments = root / "assessments.jsonl"
            output = root / "candidates.jsonl"
            tasks.write_text(
                json.dumps({"id": "one", "messages": [{"role": "developer"}, {"content": "task"}]}) + "\n",
                encoding="utf-8",
            )
            assessments.write_text(
                json.dumps({"id": "one", "prediction": {"intent": "factual_qa", "scores": {}}}) + "\n",
                encoding="utf-8",
            )
            client = _Client()
            first = run_experiment(
                tasks_path=tasks,
                assessments_path=assessments,
                output=output,
                engine="fireworks",
                model="accounts/fireworks/models/minimax-m3",
                client=client,
                max_tokens=16,
                budget_usd=1.0,
            )
            second = run_experiment(
                tasks_path=tasks,
                assessments_path=assessments,
                output=output,
                engine="fireworks",
                model="accounts/fireworks/models/minimax-m3",
                client=client,
                max_tokens=16,
                budget_usd=1.0,
            )
            row = json.loads(output.read_text())
        self.assertEqual(first["written"], 1)
        self.assertEqual(second["written"], 0)
        self.assertEqual(second["cumulative_billable_cost_usd"], first["billable_cost_usd"])
        self.assertEqual(client.calls, 1)
        self.assertEqual(row["id"], _candidate_id("one", "fireworks", row["model_id"], 16))
        self.assertEqual(row["status"], "answered")

    def test_zero_budget_stops_before_fireworks_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks.jsonl"
            assessments = root / "assessments.jsonl"
            output = root / "candidates.jsonl"
            tasks.write_text(
                json.dumps({"id": "one", "messages": [{"role": "developer"}, {"content": "task"}]}) + "\n",
                encoding="utf-8",
            )
            assessments.write_text("", encoding="utf-8")
            client = _Client()
            result = run_experiment(
                tasks_path=tasks,
                assessments_path=assessments,
                output=output,
                engine="fireworks",
                model="accounts/fireworks/models/kimi-k2p7-code",
                client=client,
                max_tokens=384,
                budget_usd=0.0,
            )
        self.assertTrue(result["stopped_for_budget"])
        self.assertEqual(client.calls, 0)

    def test_deterministic_refusal_is_not_a_runtime_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks.jsonl"
            assessments = root / "assessments.jsonl"
            output = root / "candidates.jsonl"
            tasks.write_text(
                json.dumps(
                    {
                        "id": "one",
                        "messages": [{"role": "developer"}, {"content": "Write a long novel."}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            assessments.write_text("", encoding="utf-8")
            run_experiment(
                tasks_path=tasks,
                assessments_path=assessments,
                output=output,
                engine="deterministic",
                model=None,
                client=None,
                max_tokens=1,
                budget_usd=0.0,
            )
            row = json.loads(output.read_text())
        self.assertEqual(row["status"], "refused")
        self.assertTrue(row["refusal"])
        self.assertFalse(row["failure"])

    def test_runtime_token_policy_matches_number_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks.jsonl"
            assessments = root / "assessments.jsonl"
            output = root / "candidates.jsonl"
            tasks.write_text(
                json.dumps({"id": "one", "messages": [{"role": "developer"}, {"content": "Return only the number: 42"}]}) + "\n"
            )
            assessments.write_text("")
            client = _Client()
            run_experiment(
                tasks_path=tasks,
                assessments_path=assessments,
                output=output,
                engine="fireworks",
                model="accounts/fireworks/models/minimax-m3",
                client=client,
                max_tokens=384,
                budget_usd=1.0,
                runtime_token_policy=True,
            )
            row = json.loads(output.read_text())
        self.assertEqual(client.max_tokens, [16])
        self.assertEqual(row["request_options"]["user"], "track1-token-router-v1")


if __name__ == "__main__":
    unittest.main()
