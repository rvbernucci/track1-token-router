import unittest

from scripts.fit_e2b_selective_policy import select_validation_candidate


class FitE2BSelectivePolicyTests(unittest.TestCase):
    def test_selects_strongest_local_precision_before_coverage(self) -> None:
        candidates = [
            {
                "validation_feasible": True,
                "selected_rows": 20,
                "saved_fireworks_tokens": 100,
                "local_wilson_lower_95": 0.8,
                "local_accuracy": 0.9,
                "pre_threshold": 0.3,
                "post_threshold": 0.9,
            },
            {
                "validation_feasible": True,
                "selected_rows": 30,
                "saved_fireworks_tokens": 80,
                "local_wilson_lower_95": 0.72,
                "local_accuracy": 0.8,
                "pre_threshold": 0.2,
                "post_threshold": 0.8,
            },
        ]

        selected = select_validation_candidate(candidates)

        self.assertEqual(selected["selected_rows"], 20)

    def test_never_prefers_infeasible_candidate_over_feasible_one(self) -> None:
        candidates = [
            {
                "validation_feasible": False,
                "selected_rows": 100,
                "saved_fireworks_tokens": 1000,
                "local_wilson_lower_95": 0.4,
                "local_accuracy": 0.5,
                "pre_threshold": 0.2,
                "post_threshold": 0.75,
            },
            {
                "validation_feasible": True,
                "selected_rows": 15,
                "saved_fireworks_tokens": 100,
                "local_wilson_lower_95": 0.7,
                "local_accuracy": 0.8,
                "pre_threshold": 0.5,
                "post_threshold": 0.9,
            },
        ]

        selected = select_validation_candidate(candidates)

        self.assertTrue(selected["validation_feasible"])


if __name__ == "__main__":
    unittest.main()
