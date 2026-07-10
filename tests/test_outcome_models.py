import json
import tempfile
import unittest
from pathlib import Path

from router.core.contracts import Engine, FeatureVector
from router.orchestration.outcome_models import OutcomeModelBundle, OutcomeModelPredictor


def model(correctness):
    continuous = {
        "selected_model": "constant",
        "feature_names": ["constant"],
        "coefficients": [10.0],
        "held_out_metrics": {"constant": {"observations": 10.0, "mae": 1.0, "rmse": 1.0}},
    }
    return {
        "correctness": correctness,
        "latency_ms": continuous,
        "fireworks_prompt_tokens": continuous,
        "fireworks_completion_tokens": continuous,
        "runtime_failure": {"probability": 0.01},
        "peak_memory_mb": {"value": 100.0},
    }


class OutcomeModelsTests(unittest.TestCase):
    def test_loads_with_hash_pin_and_predicts_allowed_remote_model(self):
        constant = {
            "selected_model": "constant",
            "feature_names": ["probability"],
            "coefficients": [0.8],
            "held_out_metrics": {"constant": {"observations": 10.0, "brier": 0.1}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "models.json"
            path.write_text(json.dumps({
                "schema_version": "engine-outcome-models-v1",
                "matrix_sha256": "a" * 64,
                "models": {"remote": model(constant), "gemma4-e2b": model(constant)},
            }))
            import hashlib
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            bundle = OutcomeModelBundle.load(path, expected_sha256=digest)
            predictor = OutcomeModelPredictor(bundle, allowed_models=["remote"])
            prediction = predictor.predict(FeatureVector(names=("x",), values=(0.5,)), Engine.FIREWORKS)
        self.assertEqual(prediction.probability_correct, 0.8)
        self.assertEqual(prediction.expected_fireworks_tokens, 20.0)

    def test_specific_fireworks_prediction_enforces_allowed_models(self):
        constant = {
            "selected_model": "constant",
            "feature_names": ["probability"],
            "coefficients": [0.8],
            "held_out_metrics": {"constant": {"observations": 10.0, "brier": 0.1}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "models.json"
            path.write_text(json.dumps({
                "schema_version": "engine-outcome-models-v1",
                "matrix_sha256": "a" * 64,
                "models": {"allowed": model(constant), "blocked": model(constant)},
            }))
            predictor = OutcomeModelPredictor(OutcomeModelBundle.load(path), allowed_models=["allowed"])
            features = FeatureVector(names=("x",), values=(0.5,))
            self.assertEqual(predictor.predict_fireworks_model(features, "allowed").engine, Engine.FIREWORKS)
            with self.assertRaises(ValueError):
                predictor.predict_fireworks_model(features, "blocked")

    def test_rejects_wrong_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "models.json"
            path.write_text("{}")
            with self.assertRaises(ValueError):
                OutcomeModelBundle.load(path, expected_sha256="0" * 64)

    def test_uncertainty_uses_held_out_wilson_lower_bound(self):
        constant = {
            "selected_model": "constant",
            "feature_names": ["probability"],
            "coefficients": [0.9],
            "held_out_metrics": {"constant": {"observations": 100.0, "brier": 0.1}},
            "calibration_bins": [
                {
                    "prediction_min": 0.8,
                    "prediction_max": 1.0,
                    "observations": 40.0,
                    "empirical_accuracy": 0.8,
                    "wilson_lower_95": 0.65,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "models.json"
            path.write_text(json.dumps({
                "schema_version": "engine-outcome-models-v1",
                "matrix_sha256": "a" * 64,
                "models": {"gemma4-e2b": model(constant)},
            }))
            bundle = OutcomeModelBundle.load(path)
            predictor = OutcomeModelPredictor(bundle, allowed_models=[])
            prediction = predictor.predict(FeatureVector(names=("x",), values=(0.5,)), Engine.GEMMA_E2B)
        self.assertAlmostEqual(predictor.uncertainty(prediction), 0.25)


if __name__ == "__main__":
    unittest.main()
