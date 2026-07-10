import unittest

from scripts.fit_engine_outcome_models import (
    _fit_correctness,
    _calibration_bins,
    _fold,
    _logistic_fit,
    _sigmoid,
    _split_strategy,
)


class FitEngineOutcomeModelsTests(unittest.TestCase):
    def test_lineage_fold_is_stable(self):
        self.assertEqual(_fold("lineage-a", 5), _fold("lineage-a", 5))
        self.assertIn(_fold("lineage-b", 5), range(5))

    def test_logistic_fit_learns_a_separable_signal(self):
        x = [[1.0, 0.0], [1.0, 0.1], [1.0, 0.9], [1.0, 1.0]]
        y = [0.0, 0.0, 1.0, 1.0]
        weights = _logistic_fit(x, y, l2=0.1)
        self.assertLess(_sigmoid(sum(a * b for a, b in zip(weights, x[0]))), 0.5)
        self.assertGreater(_sigmoid(sum(a * b for a, b in zip(weights, x[-1]))), 0.5)

    def test_fixed_split_selection_keeps_locked_test_separate(self):
        rows = []
        for split, values in {
            "train": [(0.0, False), (0.1, False), (0.8, True), (1.0, True)],
            "validation": [(0.2, False), (0.9, True)],
            "test": [(0.3, False), (0.7, True)],
        }.items():
            for index, (value, correct) in enumerate(values):
                rows.append(
                    {
                        "task_id": f"{split}-{index}",
                        "regression_split": split,
                        "correct": correct,
                        "features": {"names": ["signal"], "values": [value]},
                    }
                )
        result = _fit_correctness(
            rows,
            ["signal"],
            folds=5,
            l2=0.1,
            fixed_splits=True,
        )
        self.assertEqual(_split_strategy(rows), "fixed_train_validation_test")
        self.assertEqual(result["split_rows"], {"train": 4, "validation": 2, "test": 2})
        self.assertIn("locked_test_metrics", result)
        self.assertEqual(
            result["held_out_metrics"][result["selected_model"]]["observations"],
            2.0,
        )

    def test_partial_fixed_splits_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "complete fixed splits"):
            _split_strategy([{"regression_split": "train"}, {"regression_split": None}])

    def test_calibration_bins_expose_wilson_lower_bound(self):
        pairs = [(1.0, 0.9)] * 18 + [(0.0, 0.9)] * 2
        bins = _calibration_bins(pairs)
        self.assertEqual(len(bins), 1)
        self.assertEqual(bins[0]["empirical_accuracy"], 0.9)
        self.assertLess(bins[0]["wilson_lower_95"], 0.9)
        self.assertGreater(bins[0]["wilson_lower_95"], 0.6)


if __name__ == "__main__":
    unittest.main()
