import unittest

from scripts.fit_e2b_regression_v2 import (
    ABSTENTION_BAND,
    PERTURBATION_RADIUS,
    _e2b_released,
    _features,
    _logistic_fit,
    _predict,
)


ASSESSMENT = {
    "intent": "math_reasoning",
    "scores": {
        "deterministic_fit": 8,
        "reasoning_demand": 3,
        "knowledge_uncertainty": 0,
        "generation_demand": 1,
        "format_complexity": 2,
    },
}


class FitE2BRegressionV2Tests(unittest.TestCase):
    def test_input_only_feature_contract_is_bounded(self) -> None:
        features = _features("Return only the number for 2 + 2.", ASSESSMENT)
        self.assertEqual(len(features["names"]), len(features["values"]))
        self.assertLessEqual(len(features["names"]), 24)
        self.assertFalse(any("answer" in name or "verdict" in name for name in features["names"]))

    def test_e2b_probability_cannot_bypass_hard_gate(self) -> None:
        row = {
            "p_e2b": 1.0,
            "contract_valid": True,
            "category": "sentiment",
            "evidence": {"hard_gate_passed": False},
        }
        self.assertFalse(_e2b_released(row, 0.5))
        row["evidence"]["hard_gate_passed"] = True
        self.assertTrue(_e2b_released(row, 0.5))
        row["category"] = "factual_qa"
        self.assertFalse(_e2b_released(row, 0.5))

    def test_regularized_logistic_fit_learns_separable_signal(self) -> None:
        rows = [
            {"features": {"values": [0.0]}, "target": False, "mutation_lineage": "a"},
            {"features": {"values": [0.1]}, "target": False, "mutation_lineage": "b"},
            {"features": {"values": [0.9]}, "target": True, "mutation_lineage": "c"},
            {"features": {"values": [1.0]}, "target": True, "mutation_lineage": "d"},
        ]
        weights = _logistic_fit(rows, "target", l1=0.0, l2=0.5, iterations=300)
        self.assertLess(_predict(weights, [0.0]), _predict(weights, [1.0]))

    def test_frozen_stability_margins_are_at_least_two_points(self) -> None:
        self.assertGreaterEqual(PERTURBATION_RADIUS, 0.02)
        self.assertGreaterEqual(ABSTENTION_BAND, PERTURBATION_RADIUS)


if __name__ == "__main__":
    unittest.main()
