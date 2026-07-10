import json
import tempfile
import unittest
from pathlib import Path

from scripts.e2b_token_ladder import build_retry_set


class E2BTokenLadderTests(unittest.TestCase):
    def test_only_unanimous_correct_candidates_leave_the_retry_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = root / "candidates.jsonl"
            judgments = root / "judgments.jsonl"
            tasks = root / "tasks.jsonl"
            consensus = root / "consensus.jsonl"
            retry = root / "retry.jsonl"
            candidate_rows = [
                {
                    "id": f"c-{task_id}",
                    "task_id": task_id,
                    "generation_limit_tokens": 96,
                    "functiongemma_assessment": {"intent": "factual_qa", "scores": {}},
                    "answer": "answer",
                    "latency_ms": 1.0,
                    "failure": False,
                }
                for task_id in ("a", "b")
            ]
            judgment_rows = [
                {"candidate_id": "c-a", "judge_model": model, "verdict": "correct"}
                for model in ("j1", "j2")
            ] + [
                {"candidate_id": "c-b", "judge_model": "j1", "verdict": "correct"},
                {"candidate_id": "c-b", "judge_model": "j2", "verdict": "incorrect"},
            ]
            candidates.write_text("".join(json.dumps(row) + "\n" for row in candidate_rows), encoding="utf-8")
            judgments.write_text("".join(json.dumps(row) + "\n" for row in judgment_rows), encoding="utf-8")
            tasks.write_text("".join(json.dumps({"id": value}) + "\n" for value in ("a", "b")), encoding="utf-8")
            result = build_retry_set(
                candidates_path=candidates,
                judgments_path=judgments,
                tasks_path=tasks,
                judge_models=("j1", "j2"),
                consensus_output=consensus,
                retry_tasks_output=retry,
            )
            retries = [json.loads(line) for line in retry.read_text().splitlines()]
        self.assertEqual(result, {"candidates": 2, "correct": 1, "incorrect": 0, "disagree": 1, "retry_tasks": 1, "generation_limit_tokens": [96]})
        self.assertEqual(retries, [{"id": "b"}])


if __name__ == "__main__":
    unittest.main()
