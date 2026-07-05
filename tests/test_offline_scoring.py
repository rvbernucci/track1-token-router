import tempfile
import unittest
from pathlib import Path

from router.adapters.io import load_jsonl_tasks
from router.evals.offline_dataset import write_offline_dataset
from router.evals.policy_compare import compare_policies
from router.evals.scoring import ScoringWeights, build_scoreboard, write_scoreboard_report


class OfflineScoringTests(unittest.TestCase):
    def test_scoreboard_ranks_balanced_policy_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "offline"
            write_offline_dataset(root, per_category=3)
            comparison = compare_policies(load_jsonl_tasks(root / "tasks.jsonl"), root / "expected.jsonl")
            scoreboard = build_scoreboard(comparison, ScoringWeights())

        self.assertEqual(scoreboard["rows"][0]["policy"], "balanced")
        self.assertGreater(scoreboard["rows"][0]["score"], scoreboard["rows"][1]["score"])
        self.assertIn("remote_tokens_total", scoreboard["rows"][0])
        self.assertIn("budget_violations", scoreboard["rows"][0])

    def test_scoreboard_report_documents_formula(self) -> None:
        scoreboard = {
            "default_policy": "balanced",
            "weights": ScoringWeights().to_dict(),
            "formula": "score = exact_match_rate * accuracy_weight",
            "rows": [
                {
                    "rank": 1,
                    "policy": "balanced",
                    "score": 999.0,
                    "exact_match_rate": 1.0,
                    "remote_tokens_total": 50,
                    "latency_ms_total": 10,
                    "parse_failures": 0,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "scoreboard.md"
            write_scoreboard_report(report, scoreboard)
            content = report.read_text(encoding="utf-8")

        self.assertIn("Offline Scoreboard", content)
        self.assertIn("remote_token", content)


if __name__ == "__main__":
    unittest.main()
