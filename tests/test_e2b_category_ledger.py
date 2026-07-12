import unittest

from scripts.build_e2b_category_ledger import _role


class E2BCategoryLedgerTests(unittest.TestCase):
    def test_split_roles_keep_holdouts_protected(self) -> None:
        self.assertEqual(_role("train"), "fit")
        self.assertEqual(_role("validation"), "calibration")
        self.assertEqual(_role("calibration"), "calibration")
        self.assertEqual(_role("final_holdout"), "protected_holdout")


if __name__ == "__main__":
    unittest.main()
