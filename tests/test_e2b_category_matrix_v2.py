import unittest

from scripts.fit_e2b_category_matrix_v2 import (
    _auroc,
    _average_precision,
    _class_weights,
    _fit_normalization,
    _isotonic_apply,
    _isotonic_fit,
    _select_threshold,
    _subgroup_safety,
    _wilson,
    promote,
)


class E2BCategoryMatrixV2Tests(unittest.TestCase):
    def test_threshold_requires_support_precision_and_wilson(self) -> None:
        rows = [{"target": 1}] * 19
        point = _select_threshold(rows, [0.9] * 19)
        self.assertFalse(point["eligible"])
        rows = [{"target": 1}] * 20
        point = _select_threshold(rows, [0.9] * 20)
        self.assertTrue(point["eligible"])
        self.assertGreaterEqual(point["wilson_lower_95"], 0.70)

    def test_wilson_is_conservative(self) -> None:
        self.assertLess(_wilson(20, 20), 1.0)
        self.assertEqual(_wilson(0, 0), 0.0)

    def test_promotion_refuses_incomplete_holdout(self) -> None:
        with self.assertRaisesRegex(ValueError, "complete sealed"):
            promote({"artifact": {}}, [], [])

    def test_promotion_uses_support_wilson_and_difficulty_gates(self) -> None:
        artifact = {
            "allowed_intents": ["factual_qa"],
            "models_by_intent": {"factual_qa": [3.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
            "normalization_by_intent": {"factual_qa": {"mean": [0.0] * 5, "scale": [1.0] * 5}},
            "calibrators_by_intent": {"factual_qa": [0.0, 1.0]},
            "thresholds_by_intent": {"factual_qa": 0.8},
        }
        rows = []
        for index in range(480):
            rows.append({
                "source": "expansion", "role": "protected_holdout", "assessment_valid": True,
                "predicted_intent": "factual_qa" if index < 30 else "sentiment",
                "scores": {name: 5 for name in (
                    "deterministic_fit", "reasoning_demand", "knowledge_uncertainty",
                    "generation_demand", "format_complexity",
                )},
                "mechanical_features": {}, "target": 1,
                "difficulty": ("easy", "moderate", "hard")[index % 3],
            })
        result = promote({
            "artifact": artifact,
            "comparison": {"factual_qa": {"champion": "enriched"}},
        }, rows, [])
        self.assertEqual(result["promotion"]["passed_intents"], ["factual_qa"])

    def test_normalization_is_fit_from_training_values_only(self) -> None:
        rows = [{"values": [0.0, 2.0]}, {"values": [2.0, 4.0]}]
        normalization = _fit_normalization(rows, 2)
        self.assertEqual(normalization["mean"], [1.0, 3.0])
        self.assertEqual(normalization["scale"], [1.0, 1.0])

    def test_class_weights_balance_positive_and_negative_mass(self) -> None:
        targets = [1.0, 0.0, 0.0, 0.0]
        weights = _class_weights(targets)
        self.assertAlmostEqual(weights[0], sum(weights[1:]))

    def test_ranking_metrics_reward_perfect_order(self) -> None:
        rows = [{"target": 0}, {"target": 1}, {"target": 1}]
        probabilities = [0.1, 0.8, 0.9]
        self.assertEqual(_auroc(rows, probabilities), 1.0)
        self.assertEqual(_average_precision(rows, probabilities), 1.0)

    def test_subgroup_gate_rejects_hidden_low_precision_slice(self) -> None:
        rows = []
        for index in range(40):
            rows.append({
                "target": int(index < 14 or index >= 20),
                "source": "expansion", "difficulty": "easy",
                "generator_provider": "agy" if index < 20 else "fireworks",
                "mechanical_features": {
                    "mechanical.language_en": 1.0,
                    "mechanical.shape.short_text": 1.0,
                },
            })
        safe, violations = _subgroup_safety(rows)
        self.assertFalse(safe)
        self.assertTrue(any(item["dimension"] == "provider" and item["value"] == "agy" for item in violations))

    def test_isotonic_calibrator_is_monotonic(self) -> None:
        probabilities = [0.1, 0.2, 0.3, 0.4]
        rows = [{"target": value} for value in (0, 1, 0, 1)]
        model = _isotonic_fit(probabilities, rows)
        calibrated = [_isotonic_apply(model, value) for value in probabilities]
        self.assertEqual(calibrated, sorted(calibrated))


if __name__ == "__main__":
    unittest.main()
