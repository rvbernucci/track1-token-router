import unittest

from scripts.calibrate_full_hybrid_frontier import _score


class FullHybridFrontierTests(unittest.TestCase):
    def test_score_counts_validity_and_tokens(self) -> None:
        rows = [
            {"valid": True, "usage": {"total": 3}, "estimated_cost_usd": 0.1, "latency_ms": 5},
            {"valid": False, "usage": {"total": 7}, "estimated_cost_usd": 0.2, "latency_ms": 6},
        ]
        score = _score(rows)
        self.assertEqual(score["correct"], 1)
        self.assertEqual(score["accuracy"], 0.5)
        self.assertEqual(score["tokens"], 10)


if __name__ == "__main__":
    unittest.main()
