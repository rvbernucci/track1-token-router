import json
import tempfile
import unittest
from pathlib import Path

from scripts.promote_e2b_policy import _wilson_lower, promote


class PromoteE2BPolicyTests(unittest.TestCase):
    def test_wilson_lower_is_conservative(self):
        self.assertLess(_wilson_lower(18, 20), 0.9)
        self.assertGreater(_wilson_lower(18, 20), 0.6)

    def test_promotion_counts_uncertain_rows_as_not_correct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            features = {"schema_version": "feature-vector-v1", "names": ["x"], "values": [0.5]}
            rows = []
            for index in range(40):
                rows.append({
                    "regression_split": "test",
                    "engine": "gemma_e2b",
                    "model_id": "gemma4-e2b",
                    "correct": True if index < 36 else None,
                    "assessment": {"intent": "sentiment"},
                    "features": features,
                })
            matrix = root / "matrix.jsonl"
            matrix.write_text("".join(json.dumps(row) + "\n" for row in rows))
            correctness = {
                "selected_model": "constant",
                "feature_names": ["probability"],
                "coefficients": [0.9],
                "held_out_metrics": {"constant": {"observations": 100.0, "brier": 0.05}},
                "calibration_bins": [{"prediction_max": 1.0, "wilson_lower_95": 0.8}],
            }
            continuous = {"selected_model": "constant", "feature_names": ["constant"], "coefficients": [1.0]}
            model = {
                "correctness": correctness,
                "latency_ms": continuous,
                "fireworks_prompt_tokens": continuous,
                "fireworks_completion_tokens": continuous,
                "runtime_failure": {"probability": 0.01},
                "peak_memory_mb": {"value": 100.0},
            }
            models = root / "models.json"
            models.write_text(json.dumps({"schema_version": "engine-outcome-models-v1", "matrix_sha256": "a" * 64, "models": {"gemma4-e2b": model}}))
            policy = root / "policy.json"
            policy.write_text(json.dumps({"schema_version": "e2b-route-policy-v1", "default_enabled": False, "approved_intents": [], "baseline": {}, "decision_evidence": {}}))
            result = promote(
                matrix_path=matrix,
                models_path=models,
                base_policy_path=policy,
                output_policy_path=root / "output.json",
                report_path=root / "report.json",
                accuracy_gate=0.6,
                minimum_selected=30,
            )
            self.assertTrue(result["decision"]["promoted"])
            self.assertEqual(result["decision"]["disagreements_or_failures_counted_as_not_correct"], 4)


if __name__ == "__main__":
    unittest.main()
