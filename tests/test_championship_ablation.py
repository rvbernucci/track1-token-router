from __future__ import annotations

import unittest

from scripts.championship_ablation import paired_bootstrap, select_champion, summarize


class ChampionshipAblationTests(unittest.TestCase):
    def test_selects_accuracy_before_tokens(self) -> None:
        champion = select_champion(
            {
                "accurate": {"conservative_accuracy": 0.8, "fireworks_tokens": 200, "latency_ms": 20},
                "cheap": {"conservative_accuracy": 0.7, "fireworks_tokens": 10, "latency_ms": 1},
            }
        )
        self.assertEqual(champion, "accurate")

    def test_summary_counts_uncertain_as_incorrect_and_local_as_zero_token(self) -> None:
        metrics = summarize(
            [
                {"correct": True, "tokens": 10, "latency_ms": 2, "local": False, "model": "remote"},
                {"correct": None, "tokens": 0, "latency_ms": 1, "local": True, "model": "local"},
            ]
        )
        self.assertEqual(metrics["conservative_accuracy"], 0.5)
        self.assertEqual(metrics["fireworks_tokens"], 10)
        self.assertEqual(metrics["local_answers"], 1)

    def test_bootstrap_is_paired_by_lineage(self) -> None:
        champion = [
            {"task_id": "a", "lineage": "x", "correct": True, "tokens": 10},
            {"task_id": "b", "lineage": "y", "correct": False, "tokens": 20},
        ]
        challenger = [
            {"task_id": "a", "lineage": "x", "correct": True, "tokens": 5},
            {"task_id": "b", "lineage": "y", "correct": False, "tokens": 15},
        ]
        result = paired_bootstrap(challenger, champion, repetitions=100, seed=49)
        self.assertEqual(result["accuracy_delta"]["mean"], 0.0)
        self.assertEqual(result["average_token_delta"]["mean"], -5.0)


if __name__ == "__main__":
    unittest.main()
