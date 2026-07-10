import json
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_regression_learning_curve import analyze_learning_curve


class AnalyzeRegressionLearningCurveTests(unittest.TestCase):
    def test_uses_train_and_validation_without_locked_test_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            matrix = Path(directory) / "matrix.jsonl"
            rows = []
            for split, count in (("train", 40), ("validation", 12), ("test", 8)):
                for index in range(count):
                    signal = (index % 10) / 10
                    correct = signal >= 0.5
                    if split == "test":
                        correct = not correct
                    rows.append(_row(split, index, signal, correct))
            matrix.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )

            result = analyze_learning_curve(
                matrix_path=matrix,
                engine="gemma4-e2b",
                requested_sizes=[10, 20],
                repeats=3,
                l2=0.1,
                plateau_brier=0.005,
            )

            self.assertEqual(result["data"]["test_rows_present_but_unread"], 8)
            self.assertEqual([point["train_rows"] for point in result["points"]], [10, 20, 40])
            self.assertEqual(result["points"][0]["repeats"], 3)
            self.assertEqual(result["points"][-1]["repeats"], 1)
            self.assertIn(result["decision"]["best_full_train_variant"], {
                "constant", "logistic_linear", "logistic_nonlinear"
            })

    def test_requires_complete_development_splits(self):
        with tempfile.TemporaryDirectory() as directory:
            matrix = Path(directory) / "matrix.jsonl"
            matrix.write_text(json.dumps(_row("train", 0, 0.2, False)) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "train and validation"):
                analyze_learning_curve(
                    matrix_path=matrix,
                    engine="gemma4-e2b",
                    requested_sizes=[10],
                    repeats=2,
                    l2=0.1,
                    plateau_brier=0.005,
                )

    def test_locked_test_label_changes_cannot_change_learning_curve(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = root / "left.jsonl"
            right = root / "right.jsonl"
            common = []
            for split, count in (("train", 30), ("validation", 10)):
                for index in range(count):
                    signal = (index % 10) / 10
                    common.append(_row(split, index, signal, signal >= 0.5))
            left_rows = common + [_row("test", index, 0.9, True) for index in range(6)]
            right_rows = common + [_row("test", index, 0.9, False) for index in range(6)]
            left.write_text(_lines(left_rows), encoding="utf-8")
            right.write_text(_lines(right_rows), encoding="utf-8")

            kwargs = {
                "engine": "gemma4-e2b",
                "requested_sizes": [10, 20],
                "repeats": 2,
                "l2": 0.1,
                "plateau_brier": 0.005,
            }
            left_result = analyze_learning_curve(matrix_path=left, **kwargs)
            right_result = analyze_learning_curve(matrix_path=right, **kwargs)

            self.assertEqual(left_result["points"], right_result["points"])
            self.assertEqual(left_result["decision"], right_result["decision"])


def _row(split, index, signal, correct):
    return {
        "task_id": f"{split}-{index}",
        "mutation_lineage": f"{split}-lineage-{index}",
        "engine": "gemma_e2b",
        "model_id": "gemma4-e2b",
        "status": "answered",
        "correct": correct,
        "regression_split": split,
        "assessment": {"intent": "factual_qa" if index % 2 else "math_reasoning"},
        "features": {"names": ["signal"], "values": [signal]},
    }


def _lines(rows):
    return "".join(json.dumps(row) + "\n" for row in rows)


if __name__ == "__main__":
    unittest.main()
