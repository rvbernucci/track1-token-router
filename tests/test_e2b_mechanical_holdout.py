import json
import tempfile
import unittest
from pathlib import Path

from router.core.contracts import TaskEnvelope
from router.orchestration.solvers import solve_deterministic
from scripts.evaluate_e2b_mechanical_holdout import score_answer
from scripts.generate_e2b_mechanical_holdout import generate_holdout


class E2BMechanicalHoldoutTests(unittest.TestCase):
    def test_generator_is_deterministic_balanced_and_solver_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = generate_holdout(per_intent=10, seed=49, output=root / "a.jsonl", manifest=root / "a.json")
            second = generate_holdout(per_intent=10, seed=49, output=root / "b.jsonl", manifest=root / "b.json")
            rows = [json.loads(line) for line in (root / "a.jsonl").read_text(encoding="utf-8").splitlines()]

        self.assertEqual(first["rows"], 40)
        self.assertEqual(first["intent_counts"], second["intent_counts"])
        self.assertTrue(first["all_runtime_solver_refusals"])
        self.assertTrue(
            all(solve_deterministic(TaskEnvelope(id=row["id"], input_text=row["input_text"])) is None for row in rows)
        )

    def test_mechanical_scorers(self) -> None:
        self.assertEqual(score_answer({"type": "label", "expected": "positive"}, "Positive"), (True, "exact_label"))
        self.assertTrue(
            score_answer(
                {"type": "json_object", "expected": {"person": "Ava Stone"}},
                '```json\n{"person":"Ava Stone"}\n```',
            )[0]
        )
        self.assertTrue(
            score_answer(
                {"type": "exact", "expected": "The board approved Project Atlas."},
                "  The board approved Project Atlas.  ",
            )[0]
        )


if __name__ == "__main__":
    unittest.main()
