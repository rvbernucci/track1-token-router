import json
from pathlib import Path
import tempfile
import unittest

from scripts.adjudicate_e2b_expansion import _disagreement_candidates, _judge_prompt, _judge_schema


class E2BExpansionAdjudicationTests(unittest.TestCase):
    def test_judge_schema_is_bounded_and_structured(self) -> None:
        schema = _judge_schema(5)
        items = schema["properties"]["items"]
        self.assertEqual(items["minItems"], 5)
        self.assertEqual(items["maxItems"], 5)
        self.assertEqual(items["items"]["properties"]["verdict"]["enum"], ["correct", "incorrect"])

    def test_judge_prompt_blinds_router_and_generator_metadata(self) -> None:
        prompt = _judge_prompt([{
            "id": "candidate-1",
            "prompt": "Return the capital of France.",
            "answer": "Paris",
            "reference_answer": "Paris",
            "reference_rubric": "Exact city name.",
            "generator_provider": "fireworks",
            "difficulty": "easy",
            "functiongemma_assessment": {"intent": "factual_qa"},
        }])

        visible = json.loads(prompt.split("\n\n", 1)[1])
        self.assertEqual(set(visible[0]), {
            "candidate_id", "task", "candidate_answer", "reference_answer", "reference_rubric",
        })
        self.assertNotIn("fireworks", prompt)
        self.assertNotIn("functiongemma", prompt.lower())

    def test_disagreement_queue_requires_two_models_with_opposing_votes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = {
                "id": "candidate-1", "task_id": "task-1", "generator_provider": "agy",
                "eligible_judges": ["fireworks", "codex"],
            }
            self._write(root / "candidates.jsonl", [candidate])
            self._write(root / "judgments-fireworks.jsonl", [{
                "candidate_id": "candidate-1", "judge_model": "model-a", "verdict": "correct",
            }])
            self._write(root / "judgments-codex.jsonl", [{
                "candidate_id": "candidate-1", "judge_model": "model-b", "verdict": "incorrect",
            }])

            queued = _disagreement_candidates(root)

        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["eligible_judges"], ["agy"])

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
