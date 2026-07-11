import json
from pathlib import Path
import unittest

from scripts.evaluate_e2b_regression_v2_championship import _variant_metrics, check
from scripts.generate_e2b_v2_fireworks_baseline import _preferred


class E2BRegressionV2ChampionshipTests(unittest.TestCase):
    def test_remote_baseline_prefers_minimax_when_allowed(self) -> None:
        allowed = [
            "accounts/fireworks/models/kimi-k2p7-code",
            "accounts/fireworks/models/minimax-m3",
        ]
        self.assertEqual(_preferred(allowed), "accounts/fireworks/models/minimax-m3")

    def test_variant_metrics_count_only_remote_tokens_for_remote_routes(self) -> None:
        rows = [
            {
                "category": "sentiment",
                "remote_tokens": 100,
                "deterministic_release": False,
                "e2b_verifier_valid": True,
                "routes": {"full_v2": {"local": True, "correct": True}},
            },
            {
                "category": "sentiment",
                "remote_tokens": 120,
                "deterministic_release": False,
                "e2b_verifier_valid": True,
                "routes": {"full_v2": {"local": False, "correct": False}},
            },
        ]
        metrics = _variant_metrics(rows, "full_v2")
        self.assertEqual(metrics["fireworks_tokens"], 120)
        self.assertEqual(metrics["local_releases"], 1)
        self.assertEqual(metrics["local_precision"], 1.0)

    def test_final_policy_stays_disabled_after_rejection(self) -> None:
        policy = json.loads(Path("configs/e2b-local-adjudication-v2.json").read_text())
        self.assertFalse(policy["default_enabled"])
        self.assertEqual(policy["promotion"]["final_decision"], "retain_deterministic_fireworks")
        self.assertTrue(check()["passed"])


if __name__ == "__main__":
    unittest.main()
