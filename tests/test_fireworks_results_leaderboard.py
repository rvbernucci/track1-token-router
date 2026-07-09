import unittest

from scripts.fireworks_results_leaderboard import build_leaderboard, render_markdown


class FireworksResultsLeaderboardTests(unittest.TestCase):
    def test_build_leaderboard_picks_cheapest_valid_domain_winner(self) -> None:
        rows = [
            _row("math_1", "math_reasoning", "cheap-valid", valid=True, tokens=20, cost=0.00001, latency=300),
            _row("math_2", "math_reasoning", "cheap-valid", valid=True, tokens=22, cost=0.00001, latency=320),
            _row("math_1", "math_reasoning", "slow-valid", valid=True, tokens=80, cost=0.00009, latency=1400),
            _row("math_2", "math_reasoning", "slow-valid", valid=True, tokens=70, cost=0.00009, latency=1300),
            _row("math_1", "math_reasoning", "bad-cheap", valid=False, tokens=10, cost=0.000005, latency=100),
        ]

        leaderboard = build_leaderboard(rows)

        winner = leaderboard["domain_winners"]["math_reasoning"]
        self.assertEqual(winner["model"], "cheap-valid")
        self.assertEqual(winner["valid_rate"], 1.0)
        frontier = [row["model"] for row in leaderboard["domain_pareto_frontiers"]["math_reasoning"]]
        self.assertIn("cheap-valid", frontier)
        self.assertNotIn("slow-valid", frontier)

    def test_markdown_contains_domain_winners_and_failures(self) -> None:
        leaderboard = build_leaderboard(
            [
                _row("fmt_1", "formatting", "mini", valid=True, tokens=8, cost=0.00001, latency=100),
                _row("fmt_2", "formatting", "mini", valid=False, tokens=9, cost=0.00001, latency=100),
            ]
        )

        markdown = render_markdown(leaderboard)

        self.assertIn("Fireworks Results Leaderboard", markdown)
        self.assertIn("Domain Winners", markdown)
        self.assertIn("Domain Pareto Frontiers", markdown)
        self.assertIn("fmt_2", markdown)


def _row(
    task_id: str,
    domain: str,
    model: str,
    *,
    valid: bool,
    tokens: int,
    cost: float,
    latency: int,
) -> dict[str, object]:
    return {
        "id": task_id,
        "domain": domain,
        "tier": "medium",
        "model": model,
        "ok": True,
        "valid": valid,
        "usage": {"total": tokens},
        "estimated_cost_usd": cost,
        "latency_ms": latency,
        "validation_reason": "fixture",
        "error": "",
    }


if __name__ == "__main__":
    unittest.main()
