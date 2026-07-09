import tempfile
import unittest
from pathlib import Path

from router.core.contracts import TaskEnvelope
from router.orchestration.matrix_regression_selector import (
    FEATURE_NAMES,
    MatrixRegressionWeights,
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
        self.assertEqual(loaded.domain_model_stats, weights.domain_model_stats)
        self.assertEqual(len(loaded.coefficients), len(weights.coefficients))

    def test_fit_records_domain_model_empirical_stats(self) -> None:
        tasks = {
            "logic": RegressionTask(
                id="logic",
                prompt="All daxes are lims. No lims are vors. Can a dax be a vor?",
                domain="logic",
                tier="strong",
            )
        }
        rows = [
            _row("logic", "accounts/fireworks/models/minimax-m3", True, 0.00004, 900, tokens=80),
            _row("logic", "accounts/fireworks/models/kimi-k2p7-code", False, 0.00004, 900, tokens=80),
        ]

        weights = fit_matrix_regression(
            rows,
            tasks,
            allowed_models=[
                "accounts/fireworks/models/minimax-m3",
                "accounts/fireworks/models/kimi-k2p7-code",
            ],
        )

        self.assertIsNotNone(weights.domain_model_stats)
        assert weights.domain_model_stats is not None
        self.assertEqual(weights.domain_model_stats["logic"]["accounts/fireworks/models/minimax-m3"]["calls"], 1.0)
        self.assertEqual(weights.domain_model_stats["logic"]["accounts/fireworks/models/minimax-m3"]["valid"], 1.0)
        self.assertEqual(weights.domain_model_stats["logic"]["accounts/fireworks/models/kimi-k2p7-code"]["valid"], 0.0)
        self.assertIn("__overall__", weights.domain_model_stats)

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

    def test_fit_learns_token_efficiency_over_usd_cost_when_both_are_valid(self) -> None:
        tasks = {
            "factual": RegressionTask(
                id="factual",
                prompt="Who wrote Pride and Prejudice? Return only the author name.",
                domain="factual_qa",
                tier="medium",
            )
        }
        rows = [
            _row("factual", "accounts/fireworks/models/minimax-m3", True, 0.00004, 1500, tokens=180),
            _row("factual", "accounts/fireworks/models/kimi-k2p7-code", True, 0.00008, 900, tokens=55),
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
            TaskEnvelope(input_text="What is the capital of Canada? Return only the city."),
            ["minimax-m3", "kimi-k2p7-code"],
            weights,
        )

        self.assertEqual(selection["model"], "accounts/fireworks/models/kimi-k2p7-code")
        self.assertGreater(
            selection["ranked_candidates"][0]["regression_utility"],
            selection["ranked_candidates"][1]["regression_utility"],
        )

    def test_empirical_domain_risk_can_override_cheaper_base_score(self) -> None:
        weights = MatrixRegressionWeights(
            feature_names=FEATURE_NAMES,
            coefficients=[0.0 for _ in FEATURE_NAMES],
            ridge_lambda=0.35,
            training_rows=24,
            target_mean=0.90,
            observed_models=[
                "accounts/fireworks/models/minimax-m3",
                "accounts/fireworks/models/kimi-k2p7-code",
            ],
            domain_model_stats={
                "current_factual": {
                    "accounts/fireworks/models/minimax-m3": {
                        "calls": 12.0,
                        "valid": 12.0,
                        "valid_rate": 1.0,
                        "valid_rate_smoothed": 0.98,
                        "confidence": 0.75,
                    },
                    "accounts/fireworks/models/kimi-k2p7-code": {
                        "calls": 12.0,
                        "valid": 3.0,
                        "valid_rate": 0.25,
                        "valid_rate_smoothed": 0.35,
                        "confidence": 0.75,
                    },
                }
            },
        )

        selection = select_model_by_matrix_regression(
            TaskEnvelope(input_text="Who wrote Pride and Prejudice? Return only the author name."),
            ["minimax-m3", "kimi-k2p7-code"],
            weights,
        )

        self.assertEqual(selection["model"], "accounts/fireworks/models/minimax-m3")
        self.assertGreater(
            selection["ranked_candidates"][0]["hybrid_score"],
            selection["ranked_candidates"][1]["hybrid_score"],
        )
        self.assertGreater(
            selection["ranked_candidates"][1]["base_hybrid_score"],
            selection["ranked_candidates"][1]["hybrid_score"],
        )
        self.assertEqual(selection["ranked_candidates"][0]["empirical_calls"], 12.0)

    def test_empirical_token_prediction_overrides_static_token_profile(self) -> None:
        weights = MatrixRegressionWeights(
            feature_names=FEATURE_NAMES,
            coefficients=[0.0 for _ in FEATURE_NAMES],
            ridge_lambda=0.35,
            training_rows=40,
            target_mean=0.95,
            observed_models=[
                "accounts/fireworks/models/minimax-m3",
                "accounts/fireworks/models/kimi-k2p7-code",
            ],
            domain_model_stats={
                "classification": {
                    "accounts/fireworks/models/minimax-m3": {
                        "calls": 20.0,
                        "valid": 20.0,
                        "valid_rate": 1.0,
                        "valid_rate_smoothed": 0.99,
                        "confidence": 0.83,
                        "avg_total_tokens": 35.0,
                    },
                    "accounts/fireworks/models/kimi-k2p7-code": {
                        "calls": 20.0,
                        "valid": 20.0,
                        "valid_rate": 1.0,
                        "valid_rate_smoothed": 0.99,
                        "confidence": 0.83,
                        "avg_total_tokens": 400.0,
                    },
                }
            },
        )

        selection = select_model_by_matrix_regression(
            TaskEnvelope(input_text="Classify the sentiment as positive, neutral, or negative. Text: Great."),
            ["minimax-m3", "kimi-k2p7-code"],
            weights,
        )
        ranked = selection["ranked_candidates"]

        self.assertEqual(selection["model"], "accounts/fireworks/models/minimax-m3")
        self.assertGreater(ranked[0]["predicted_token_utility"], ranked[1]["predicted_token_utility"])
        self.assertLess(ranked[0]["token_utility"], ranked[1]["token_utility"])
        self.assertGreater(ranked[1]["predicted_total_tokens"], ranked[0]["predicted_total_tokens"])

    def test_shape_specific_empirical_risk_overrides_domain_average(self) -> None:
        weights = MatrixRegressionWeights(
            feature_names=FEATURE_NAMES,
            coefficients=[0.0 for _ in FEATURE_NAMES],
            ridge_lambda=0.35,
            training_rows=48,
            target_mean=0.95,
            observed_models=[
                "accounts/fireworks/models/minimax-m3",
                "accounts/fireworks/models/kimi-k2p7-code",
            ],
            domain_model_stats={
                "summarization": {
                    "accounts/fireworks/models/minimax-m3": {
                        "calls": 20.0,
                        "valid": 20.0,
                        "valid_rate": 1.0,
                        "valid_rate_smoothed": 0.99,
                        "confidence": 0.83,
                        "avg_total_tokens": 180.0,
                    },
                    "accounts/fireworks/models/kimi-k2p7-code": {
                        "calls": 20.0,
                        "valid": 20.0,
                        "valid_rate": 1.0,
                        "valid_rate_smoothed": 0.99,
                        "confidence": 0.83,
                        "avg_total_tokens": 70.0,
                    },
                },
                "summarization::constrained_summary": {
                    "accounts/fireworks/models/minimax-m3": {
                        "calls": 12.0,
                        "valid": 12.0,
                        "valid_rate": 1.0,
                        "valid_rate_smoothed": 0.98,
                        "confidence": 0.75,
                        "avg_total_tokens": 190.0,
                    },
                    "accounts/fireworks/models/kimi-k2p7-code": {
                        "calls": 12.0,
                        "valid": 4.0,
                        "valid_rate": 0.33,
                        "valid_rate_smoothed": 0.45,
                        "confidence": 0.75,
                        "avg_total_tokens": 65.0,
                    },
                },
            },
        )

        selection = select_model_by_matrix_regression(
            TaskEnvelope(input_text="Summarize in at most 8 words and include latency: Local checks reduce remote calls."),
            ["minimax-m3", "kimi-k2p7-code"],
            weights,
        )
        ranked = selection["ranked_candidates"]

        self.assertEqual(selection["model"], "accounts/fireworks/models/minimax-m3")
        self.assertEqual(ranked[0]["features"]["shape_constrained_summary"], 1.0)
        self.assertLess(ranked[1]["empirical_valid_rate_smoothed"], ranked[0]["empirical_valid_rate_smoothed"])


def _row(task_id: str, model: str, valid: bool, cost: float, latency_ms: int, *, tokens: int = 100) -> dict[str, object]:
    return {
        "id": task_id,
        "model": model,
        "valid": valid,
        "ok": True,
        "usage": {"total": tokens},
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
        self.assertGreaterEqual(weights.training_rows, 100)
        self.assertIsNotNone(weights.domain_model_stats)
        assert weights.domain_model_stats is not None
        self.assertIn("summarization", weights.domain_model_stats)
        self.assertIn("accounts/fireworks/models/kimi-k2p7-code", weights.domain_model_stats["summarization"])

    def test_checked_in_track1_weights_route_common_hidden_variants(self) -> None:
        weights = load_weights(Path("router/data/fireworks_track1_allowed_weights.json"))
        allowed = ["minimax-m3", "kimi-k2p7-code", "gemma-4-31b-it", "gemma-4-26b-a4b-it", "gemma-4-31b-it-nvfp4"]

        cases = [
            (
                "Who wrote Pride and Prejudice? Return only the author name.",
                "current_factual",
                "accounts/fireworks/models/kimi-k2p7-code",
            ),
            (
                "Summarize in at most 8 words: Token-efficient routing preserves accuracy while reducing paid model calls.",
                "summarization",
                "accounts/fireworks/models/kimi-k2p7-code",
            ),
            (
                "Classify the sentiment as exactly one word: positive, neutral, or negative. Text: The UI looks elegant, but the export failed twice and wasted my time.",
                "classification",
                "accounts/fireworks/models/minimax-m3",
            ),
            (
                "Compute 17 * 6 + 4. Return only the number.",
                "math_reasoning",
                "accounts/fireworks/models/kimi-k2p7-code",
            ),
            (
                "Return only minified JSON. Given values [17, 4, 23, 9], return min and max.",
                "math_reasoning",
                "accounts/fireworks/models/kimi-k2p7-code",
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
                "Return only minified JSON. Extract name, email, and phone from: Contact Lara at lara.silva@example.com or +55-11-99888-7766.",
                "extraction",
                "accounts/fireworks/models/minimax-m3",
            ),
            (
                "All merls are tivas. Some tivas are roons. Is it guaranteed that some merls are roons? Return exactly yes or no.",
                "logic",
                "accounts/fireworks/models/kimi-k2p7-code",
            ),
        ]

        for prompt, expected_domain, expected_model in cases:
            with self.subTest(prompt=prompt):
                selection = select_model_by_matrix_regression(TaskEnvelope(input_text=prompt), allowed, weights)

                self.assertEqual(selection["domain"], expected_domain)
                self.assertEqual(selection["model"], expected_model)
                self.assertIn("predicted_total_tokens", selection["ranked_candidates"][0])
                self.assertIn("predicted_token_utility", selection["ranked_candidates"][0])

    def test_dockerfile_enables_checked_in_track1_weights(self) -> None:
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

        self.assertIn("FIREWORKS_MATRIX_WEIGHTS=/app/router/data/fireworks_track1_allowed_weights.json", dockerfile)
        self.assertIn("COPY router ./router", dockerfile)


if __name__ == "__main__":
    unittest.main()
