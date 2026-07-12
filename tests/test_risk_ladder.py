import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from router.orchestration.risk_ladder import RiskLadderPolicy, SAFETY_ORDER, wilson_lower


POLICY = Path("configs/wilson-nash-risk-ladder-v1.json")


class RiskLadderTests(unittest.TestCase):
    def test_confidence_level_is_not_the_lower_bound(self) -> None:
        lower = wilson_lower(44, 46, confidence=0.90)
        self.assertAlmostEqual(lower, 0.8768185086792523)
        self.assertNotEqual(lower, 0.90)
        self.assertLess(wilson_lower(44, 46, confidence=0.95), lower)

    def test_unknown_intent_fails_closed(self) -> None:
        decision = RiskLadderPolicy.load(POLICY).decide(intent="math_reasoning", probability=0.99, remaining_ms=60000)
        self.assertEqual(decision.action, "fireworks")

    def test_sentiment_uses_nash_tier_without_review(self) -> None:
        decision = RiskLadderPolicy.load(POLICY).decide(intent="sentiment", probability=0.96, remaining_ms=60000)
        self.assertEqual(decision.tier, "nash_minimax")
        self.assertIn(decision.action, {"e2b", "fireworks"})
        self.assertTrue(decision.candidates)

    def test_evidence_does_not_leak_below_frozen_decision_surface(self) -> None:
        decision = RiskLadderPolicy.load(POLICY).decide(
            intent="sentiment", probability=0.764464, remaining_ms=60000,
        )
        self.assertEqual(decision.action, "fireworks")
        self.assertEqual(decision.reason, "outside_evidence_decision_surface")

    def test_deadline_never_enables_review(self) -> None:
        payload = json.loads(POLICY.read_text())
        payload["review_enabled"] = True
        payload["evidence_by_intent"]["sentiment"]["successes"] = 36
        payload["evidence_by_intent"]["sentiment"]["support"] = 46
        with TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps(payload))
            policy = RiskLadderPolicy.load(path)
            self.assertEqual(policy.decide(intent="sentiment", probability=0.8, remaining_ms=1000).action, "fireworks")

    def test_decreasing_support_cannot_make_route_less_safe(self) -> None:
        decisions = []
        for support in (200, 100, 50, 25):
            payload = json.loads(POLICY.read_text())
            payload["evidence_by_intent"]["sentiment"].update(successes=round(0.95 * support), support=support)
            with TemporaryDirectory() as directory:
                path = Path(directory) / "policy.json"
                path.write_text(json.dumps(payload))
                decisions.append(RiskLadderPolicy.load(path).decide(
                    intent="sentiment", probability=0.95, remaining_ms=60000,
                ).action)
        ranks = [SAFETY_ORDER[action] for action in decisions]
        self.assertEqual(ranks, sorted(ranks))


if __name__ == "__main__":
    unittest.main()
