import unittest

from scripts.consolidate_e2b_contract_judgments import _majority, _matrix_verdict


class ConsolidateE2BContractJudgmentsTests(unittest.TestCase):
    def test_majority_preserves_unresolved_three_way_split(self) -> None:
        self.assertEqual(_majority(["correct", "correct", "incorrect"]), "correct")
        self.assertEqual(_majority(["correct", "incorrect", "uncertain"]), "uncertain")

    def test_matrix_verdict_requires_explicit_unanimity(self) -> None:
        self.assertEqual(_matrix_verdict({"consensus": "unanimous_correct", "correct": True}), "correct")
        self.assertEqual(_matrix_verdict({"consensus": "unanimous_incorrect", "correct": False}), "incorrect")
        self.assertEqual(_matrix_verdict({"consensus": "disagree", "correct": None}), "uncertain")


if __name__ == "__main__":
    unittest.main()
