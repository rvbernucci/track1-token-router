from pathlib import Path
import unittest

from scripts.run_e2b_contract_population import population


class ContractPopulationTests(unittest.TestCase):
    def test_population_is_complete_and_unique(self) -> None:
        result = population(Path.cwd())
        self.assertEqual(len(result), 4400)
        self.assertEqual(len({row["task_id"] for row in result}), 4400)
        self.assertEqual({row["role"] for row in result}, {"fit", "calibration", "protected_holdout"})
        self.assertTrue(all(row["prompt"] and row["reference_rubric"] for row in result))


if __name__ == "__main__":
    unittest.main()
