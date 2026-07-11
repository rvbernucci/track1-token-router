import unittest
from pathlib import Path

from router.core.contracts import AssessmentScores, Intent, TaskAssessment
from router.orchestration.e2b_matrix_gate import E2BMatrixGate


class E2BMatrixGateTests(unittest.TestCase):
    def test_promoted_policy_produces_bounded_decision(self) -> None:
        gate = E2BMatrixGate.load(Path("configs/e2b-270m-matrix-regression.json"))
        assessment = TaskAssessment(
            intent=Intent.SENTIMENT,
            scores=AssessmentScores(
                deterministic_fit=7,
                reasoning_demand=1,
                knowledge_uncertainty=1,
                generation_demand=1,
                format_complexity=1,
            ),
        )
        decision = gate.decide(assessment)
        self.assertTrue(gate.enabled)
        self.assertGreaterEqual(decision.probability, 0.0)
        self.assertLessEqual(decision.probability, 1.0)
        self.assertEqual(decision.probe, decision.probability >= decision.threshold)

    def test_hash_mismatch_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            E2BMatrixGate.load(
                Path("configs/e2b-270m-matrix-regression.json"),
                expected_sha256="0" * 64,
            )

    def test_boundary_audit_restriction_fails_closed_for_other_intents(self) -> None:
        gate = E2BMatrixGate.load(Path("configs/e2b-270m-matrix-regression.json"))
        assessment = TaskAssessment(
            intent=Intent.SUMMARIZATION,
            scores=AssessmentScores(
                deterministic_fit=10,
                reasoning_demand=0,
                knowledge_uncertainty=0,
                generation_demand=0,
                format_complexity=0,
            ),
        )
        decision = gate.decide(assessment)
        self.assertFalse(decision.probe)
        self.assertEqual(decision.reason, "matrix_disabled_or_unknown_intent")


if __name__ == "__main__":
    unittest.main()
