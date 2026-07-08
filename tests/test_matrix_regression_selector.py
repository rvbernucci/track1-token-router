import tempfile
import unittest
from pathlib import Path

from router.core.contracts import TaskEnvelope
from router.orchestration.matrix_regression_selector import (
    RegressionTask,
    fit_matrix_regression,
    load_weights,
    save_weights,
    select_model_by_matrix_regression,
)


class MatrixRegressionSelectorTests(unittest.TestCase):
    def test_fit_prefers_model_with_valid_observations(self) -> None:
        tasks = {
            "sentiment": RegressionTask(
                id="sentiment",
                prompt="Classify sentiment as positive, neutral, or negative: I love it.",
                domain="classification",
                tier="cheap",
            ),
            "json": RegressionTask(
                id="json",
                prompt="Return only minified JSON with status=ready.",
                domain="formatting",
                tier="cheap",
            ),
            "math": RegressionTask(
                id="math",
                prompt="A plan costs 80, has 15 percent discount, then 5 fee. Return only number.",
                domain="math_reasoning",
                tier="strong",
            ),
        }
        rows = [
            _row("sentiment", "accounts/fireworks/models/deepseek-v4-flash", True, 0.000008, 800),
            _row("sentiment", "accounts/fireworks/models/qwen3p7-plus", False, 0.000030, 1300),
            _row("json", "accounts/fireworks/models/deepseek-v4-flash", True, 0.000009, 900),
            _row("json", "accounts/fireworks/models/qwen3p7-plus", False, 0.000040, 1400),
            _row("math", "accounts/fireworks/models/deepseek-v4-flash", True, 0.000030, 1700),
            _row("math", "accounts/fireworks/models/qwen3p7-plus", False, 0.000180, 1600),
        ]

        weights = fit_matrix_regression(
            rows,
            tasks,
            allowed_models=[
                "accounts/fireworks/models/deepseek-v4-flash",
                "accounts/fireworks/models/qwen3p7-plus",
            ],
        )
        selection = select_model_by_matrix_regression(
            TaskEnvelope(input_text="Classify sentiment as positive, neutral, or negative: excellent."),
            [
                "accounts/fireworks/models/deepseek-v4-flash",
                "accounts/fireworks/models/qwen3p7-plus",
            ],
            weights,
        )

        self.assertEqual(selection["model"], "accounts/fireworks/models/deepseek-v4-flash")
        self.assertEqual(selection["selection_rule"], "matrix_regression_plus_nash")
        self.assertGreater(selection["ranked_candidates"][0]["hybrid_score"], selection["ranked_candidates"][1]["hybrid_score"])

    def test_weights_roundtrip(self) -> None:
        tasks = {
            "sentiment": RegressionTask(
                id="sentiment",
                prompt="Classify sentiment as positive, neutral, or negative: I love it.",
                domain="classification",
                tier="cheap",
            )
        }
        rows = [
            _row("sentiment", "accounts/fireworks/models/deepseek-v4-flash", True, 0.000008, 800),
            _row("sentiment", "accounts/fireworks/models/qwen3p7-plus", False, 0.000030, 1300),
        ]
        weights = fit_matrix_regression(
            rows,
            tasks,
            allowed_models=[
                "accounts/fireworks/models/deepseek-v4-flash",
                "accounts/fireworks/models/qwen3p7-plus",
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "weights.json"
            save_weights(weights, path)
            loaded = load_weights(path)

        self.assertEqual(loaded.feature_names, weights.feature_names)
        self.assertEqual(loaded.training_rows, weights.training_rows)
        self.assertEqual(len(loaded.coefficients), len(weights.coefficients))


def _row(task_id: str, model: str, valid: bool, cost: float, latency_ms: int) -> dict[str, object]:
    return {
        "id": task_id,
        "model": model,
        "valid": valid,
        "estimated_cost_usd": cost,
        "latency_ms": latency_ms,
        "request_options": {"user": "test"},
    }


if __name__ == "__main__":
    unittest.main()
