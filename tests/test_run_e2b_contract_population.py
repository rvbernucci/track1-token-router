from pathlib import Path
import unittest

from scripts.run_e2b_contract_population import population


class ContractPopulationTests(unittest.TestCase):
    def test_public_development_population_is_complete_and_unique(self) -> None:
        result = population(Path.cwd(), include_protected=False)
        self.assertEqual(len(result), 3520)
        self.assertEqual(len({row["task_id"] for row in result}), 3520)
        self.assertEqual({row["role"] for row in result}, {"fit", "calibration"})
        self.assertTrue(all(row["prompt"] and row["reference_rubric"] for row in result))

    def test_authorized_population_includes_sealed_holdout(self) -> None:
        root = Path.cwd()
        sealed = (
            root / "evals/e2b-expansion-v1/sealed/tasks/final_holdout.jsonl",
            root / "evals/e2b-expansion-v1/sealed/references/final_holdout.jsonl",
            root / "evals/e2b-regression-v2/sealed/final_holdout.jsonl",
        )
        if not all(path.is_file() for path in sealed):
            self.skipTest("sealed holdout is intentionally absent from public checkouts")
        result = population(root)
        self.assertEqual(len(result), 4400)
        self.assertEqual(len({row["task_id"] for row in result}), 4400)
        self.assertEqual({row["role"] for row in result}, {"fit", "calibration", "protected_holdout"})
        self.assertTrue(all(row["prompt"] and row["reference_rubric"] for row in result))


if __name__ == "__main__":
    unittest.main()
