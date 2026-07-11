import unittest

from scripts.analyze_e2b_routing_cohorts import _scenario_metrics


class AnalyzeE2BRoutingCohortsTests(unittest.TestCase):
    def test_scenario_weights_compute_distribution_dependent_coverage(self) -> None:
        cohorts = {
            "sentiment": {"coverage": 0.5, "precision": 0.9},
            "code": {"coverage": 0.0, "precision": None},
        }

        result = _scenario_metrics({"sentiment": 0.8, "code": 0.2}, cohorts, 200.0)

        self.assertAlmostEqual(result["expected_local_coverage"], 0.4)
        self.assertAlmostEqual(result["expected_local_precision"], 0.9)
        self.assertAlmostEqual(result["expected_fireworks_tokens_saved_per_100"], 8000.0)


if __name__ == "__main__":
    unittest.main()
