import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.judge_engine_outcomes import _judge_prompt, _response_schema, run_judging
from router.dataset_forge.providers import ProviderError


class _Provider:
    model = "accounts/fireworks/models/test-teacher"

    def estimate_upper_bound_usd(self, _prompt):
        return 0.01

    def invoke(self, *, prompt, response_schema, role):
        request = json.loads(prompt.split("\n\n", 1)[1])
        judgments = [
            {
                "id": item["id"],
                "verdict": "correct",
                "confidence": 0.9,
                "format_valid": True,
                "rationale": "The answer is exact.",
            }
            for item in request["items"]
        ]
        provenance = SimpleNamespace(
            model=self.model,
            billable_cost_usd=0.002,
            to_dict=lambda: {
                "model": self.model,
                "role": role,
                "billable_cost_usd": 0.002,
                "request_id": "request-one",
            },
        )
        return SimpleNamespace(payload={"judgments": judgments}, provenance=provenance)


class _SubscriptionProvider(_Provider):
    estimate_upper_bound_usd = None


class _SplitProvider(_SubscriptionProvider):
    def invoke(self, *, prompt, response_schema, role):
        request = json.loads(prompt.split("\n\n", 1)[1])
        if len(request["items"]) > 2:
            raise ProviderError("simulated oversized batch")
        return super().invoke(prompt=prompt, response_schema=response_schema, role=role)


class _MalformedBatchProvider(_SubscriptionProvider):
    def invoke(self, *, prompt, response_schema, role):
        request = json.loads(prompt.split("\n\n", 1)[1])
        if len(request["items"]) > 2:
            invocation = super().invoke(prompt=prompt, response_schema=response_schema, role=role)
            return SimpleNamespace(payload={"judgments": []}, provenance=invocation.provenance)
        return super().invoke(prompt=prompt, response_schema=response_schema, role=role)


class JudgeEngineOutcomesTests(unittest.TestCase):
    def test_schema_pins_ids_and_batch_size(self):
        schema = _response_schema(["a", "b"])
        judgments = schema["properties"]["judgments"]
        self.assertEqual(judgments["minItems"], 2)
        self.assertEqual(judgments["items"]["properties"]["id"]["enum"], ["a", "b"])

    def test_run_is_budgeted_append_only_and_resumable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.jsonl"
            output = root / "judgments.jsonl"
            rows = [
                {
                    "id": item,
                    "task_text": "2+2?",
                    "answer": "4",
                    "engine": "gemma_e2b",
                    "engine_version": "v1",
                    "failure": False,
                    "functiongemma_assessment": {"intent": "math_reasoning"},
                }
                for item in ("a", "b")
            ]
            candidates.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            first = run_judging(
                candidates_path=candidates,
                output=output,
                provider=_Provider(),
                batch_size=2,
                budget_usd=0.02,
            )
            second = run_judging(
                candidates_path=candidates,
                output=output,
                provider=_Provider(),
                batch_size=2,
                budget_usd=0.02,
            )
        self.assertEqual(first["written"], 2)
        self.assertEqual(first["billable_cost_usd"], 0.002)
        self.assertEqual(second["written"], 0)
        self.assertEqual(second["cumulative_billable_cost_usd"], 0.002)

    def test_subscription_provider_without_usd_estimator_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.jsonl"
            output = root / "judgments.jsonl"
            candidates.write_text(
                json.dumps(
                    {
                        "id": "a",
                        "task_text": "2+2?",
                        "answer": "4",
                        "engine": "gemma_e2b",
                        "engine_version": "v1",
                        "failure": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = run_judging(
                candidates_path=candidates,
                output=output,
                provider=_SubscriptionProvider(),
                batch_size=1,
                budget_usd=0.0,
            )
        self.assertEqual(result["written"], 1)
        self.assertEqual(result["billable_cost_usd"], 0.002)

    def test_missing_assessment_produces_null_intent_hint(self):
        prompt = _judge_prompt([
            {"id": "candidate", "task_text": "2+2?", "answer": "4", "functiongemma_assessment": None}
        ])
        payload = json.loads(prompt.split("\n\n", 1)[1])
        self.assertIsNone(payload["items"][0]["intent_hint"])

    def test_oversized_batches_split_without_losing_completed_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.jsonl"
            output = root / "judgments.jsonl"
            rows = [
                {
                    "id": f"candidate-{index}",
                    "task_text": "2+2?",
                    "answer": "4",
                    "engine": "gemma_e2b",
                    "engine_version": "v1",
                    "failure": False,
                }
                for index in range(5)
            ]
            candidates.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

            result = run_judging(
                candidates_path=candidates,
                output=output,
                provider=_SplitProvider(),
                batch_size=5,
                budget_usd=0.0,
            )

            persisted = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(result["written"], 5)
        self.assertEqual(result["remaining"], 0)
        self.assertGreater(result["adaptive_splits"], 0)
        self.assertEqual(len({row["candidate_id"] for row in persisted}), 5)

    def test_malformed_large_response_splits_and_recovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.jsonl"
            output = root / "judgments.jsonl"
            rows = [
                {
                    "id": f"candidate-{index}",
                    "task_text": "2+2?",
                    "answer": "4",
                    "engine": "gemma_e2b",
                    "engine_version": "v1",
                    "failure": False,
                }
                for index in range(5)
            ]
            candidates.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

            result = run_judging(
                candidates_path=candidates,
                output=output,
                provider=_MalformedBatchProvider(),
                batch_size=5,
                budget_usd=0.0,
            )

        self.assertEqual(result["written"], 5)
        self.assertEqual(result["remaining"], 0)
        self.assertGreater(result["adaptive_splits"], 0)


if __name__ == "__main__":
    unittest.main()
