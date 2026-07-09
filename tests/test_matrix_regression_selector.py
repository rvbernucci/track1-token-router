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
        self.assertEqual(loaded.observed_models, weights.observed_models)
        self.assertEqual(len(loaded.coefficients), len(weights.coefficients))

    def test_selection_filters_unobserved_allowed_models_when_possible(self) -> None:
        tasks = {
            "sentiment": RegressionTask(
                id="sentiment",
                prompt="Classify sentiment as positive, neutral, or negative: I love it.",
                domain="classification",
                tier="cheap",
            )
        }
        rows = [
            _row("sentiment", "accounts/fireworks/models/minimax-m3", True, 0.00005, 1000),
            _row("sentiment", "accounts/fireworks/models/kimi-k2p7-code", True, 0.00007, 700),
        ]
        weights = fit_matrix_regression(
            rows,
            tasks,
            allowed_models=[
                "accounts/fireworks/models/minimax-m3",
                "accounts/fireworks/models/kimi-k2p7-code",
            ],
        )

        selection = select_model_by_matrix_regression(
            TaskEnvelope(input_text="Classify sentiment as positive, neutral, or negative: excellent."),
            ["gemma-4-31b-it-nvfp4", "minimax-m3", "kimi-k2p7-code"],
            weights,
        )

        ranked_models = {candidate["model"] for candidate in selection["ranked_candidates"]}
        self.assertNotIn("accounts/fireworks/models/gemma-4-31b-it-nvfp4", ranked_models)
        self.assertIn(selection["model"], weights.observed_models)


def _row(task_id: str, model: str, valid: bool, cost: float, latency_ms: int) -> dict[str, object]:
    return {
        "id": task_id,
        "model": model,
        "valid": valid,
        "estimated_cost_usd": cost,
        "latency_ms": latency_ms,
        "request_options": {"user": "test"},
    }


class CheckedInTrack1WeightsTests(unittest.TestCase):
    def test_checked_in_track1_weights_are_loadable_and_select_allowed_model(self) -> None:
        weights = load_weights(Path("router/data/fireworks_track1_allowed_weights.json"))
        selection = select_model_by_matrix_regression(
            TaskEnvelope(
                id="code",
                input_text="Return only Python code. Define a function clamp(value, low, high).",
            ),
            ["minimax-m3", "kimi-k2p7-code", "gemma-4-31b-it"],
            weights,
        )

        self.assertIn(
            selection["model"],
            {
                "accounts/fireworks/models/minimax-m3",
                "accounts/fireworks/models/kimi-k2p7-code",
                "accounts/fireworks/models/gemma-4-31b-it",
            },
        )
        self.assertEqual(selection["selection_rule"], "matrix_regression_plus_nash")

    def test_checked_in_track1_weights_route_common_hidden_variants(self) -> None:
        weights = load_weights(Path("router/data/fireworks_track1_allowed_weights.json"))
        allowed = ["minimax-m3", "kimi-k2p7-code", "gemma-4-31b-it", "gemma-4-26b-a4b-it", "gemma-4-31b-it-nvfp4"]

        cases = [
            (
                "Compute 17 * 6 + 4. Return only the number.",
                "math_reasoning",
                "accounts/fireworks/models/minimax-m3",
            ),
            (
                "Return only minified JSON. Given values [17, 4, 23, 9], return min and max.",
                "math_reasoning",
                "accounts/fireworks/models/minimax-m3",
            ),
            (
                "Fix this Python code: def add(a, b): return a - b",
                "code_debug",
                "accounts/fireworks/models/minimax-m3",
            ),
            (
                "Write a Python function add(a, b) that returns the sum.",
                "code_generation",
                "accounts/fireworks/models/minimax-m3",
            ),
            (
                "All merls are tivas. Some tivas are roons. Is it guaranteed that some merls are roons? Return exactly yes or no.",
                "logic",
                "accounts/fireworks/models/minimax-m3",
            ),
        ]

        for prompt, expected_domain, expected_model in cases:
            with self.subTest(prompt=prompt):
                selection = select_model_by_matrix_regression(TaskEnvelope(input_text=prompt), allowed, weights)

                self.assertEqual(selection["domain"], expected_domain)
                self.assertEqual(selection["model"], expected_model)

    def test_dockerfile_enables_checked_in_track1_weights(self) -> None:
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

        self.assertIn("FIREWORKS_MATRIX_WEIGHTS=/app/router/data/fireworks_track1_allowed_weights.json", dockerfile)
        self.assertIn("COPY router ./router", dockerfile)


if __name__ == "__main__":
    unittest.main()
