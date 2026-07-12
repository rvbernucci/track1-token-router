import unittest
import json
from pathlib import Path
import tempfile

from router.core.contracts import AssessmentScores, Intent, TaskAssessment
from router.orchestration.e2b_matrix_gate import E2BMatrixGate


class E2BMatrixGateTests(unittest.TestCase):
    def test_promoted_v2_policy_loads_with_sentiment_only(self) -> None:
        gate = E2BMatrixGate.load(Path("configs/e2b-category-matrix-regression-v2.json"))
        self.assertTrue(gate.enabled)
        self.assertEqual(gate.allowed_intents, frozenset({"sentiment"}))
        self.assertIsNotNone(gate.normalization_by_intent)

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

    def test_sentiment_explanation_is_never_sent_to_label_only_e2b_cohort(self) -> None:
        gate = E2BMatrixGate.load(Path("configs/e2b-category-matrix-regression-v2.json"))
        assessment = TaskAssessment(
            intent=Intent.SENTIMENT,
            scores=AssessmentScores(5, 3, 0, 4, 2),
        )

        decision = gate.decide(
            assessment,
            "Classify as Positive, Negative, or Neutral and give a one-sentence reason.",
        )

        self.assertFalse(decision.probe)
        self.assertEqual(decision.reason, "matrix_explanatory_response_required")

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

    def test_v2_uses_per_intent_threshold_and_mechanical_prompt_feature(self) -> None:
        policy = {
            "schema_version": "e2b-category-matrix-regression-v2",
            "default_enabled": True,
            "decision_threshold": 0.99,
            "score_feature_names": [
                "deterministic_fit", "reasoning_demand", "knowledge_uncertainty",
                "generation_demand", "format_complexity",
            ],
            "mechanical_feature_names": ["mechanical.strict_format"],
            "models_by_intent": {
                intent.value: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 4.0]
                for intent in Intent
            },
            "thresholds_by_intent": {intent.value: 0.9 for intent in Intent},
            "calibrators_by_intent": {intent.value: [0.0, 1.0] for intent in Intent},
            "normalization_by_intent": {
                intent.value: {"mean": [0.0] * 6, "scale": [1.0] * 6}
                for intent in Intent
            },
            "allowed_intents": ["summarization"],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps(policy), encoding="utf-8")
            gate = E2BMatrixGate.load(path)
            assessment = TaskAssessment(
                intent=Intent.SUMMARIZATION,
                scores=AssessmentScores(1, 1, 1, 1, 1),
            )
            accepted = gate.decide(assessment, "Summarize this text. Return only one sentence. Text: Stable input.")
            self.assertTrue(accepted.probe)
            self.assertEqual(accepted.threshold, 0.9)
            self.assertEqual(accepted.feature_schema_version, "e2b-mechanical-features-v2")
            missing = gate.decide(assessment)
            self.assertFalse(missing.probe)
            self.assertEqual(missing.reason, "matrix_missing_mechanical_features")

    def test_v2_applies_distinct_category_thresholds(self) -> None:
        intents = list(Intent)
        dimensions = 5 + 1
        policy = {
            "schema_version": "e2b-category-matrix-regression-v2",
            "default_enabled": True,
            "decision_threshold": 1.0,
            "score_feature_names": [
                "deterministic_fit", "reasoning_demand", "knowledge_uncertainty",
                "generation_demand", "format_complexity",
            ],
            "mechanical_feature_names": ["mechanical.strict_format"],
            "models_by_intent": {intent.value: [0.0] * (dimensions + 1) for intent in intents},
            "thresholds_by_intent": {
                intent.value: (0.4 if intent is Intent.FACTUAL_QA else 0.6) for intent in intents
            },
            "calibrators_by_intent": {intent.value: [0.0, 1.0] for intent in intents},
            "normalization_by_intent": {
                intent.value: {"mean": [0.0] * dimensions, "scale": [1.0] * dimensions}
                for intent in intents
            },
            "allowed_intents": [Intent.FACTUAL_QA.value, Intent.SUMMARIZATION.value],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps(policy), encoding="utf-8")
            gate = E2BMatrixGate.load(path)
            scores = AssessmentScores(1, 1, 1, 1, 1)
            factual = gate.decide(TaskAssessment(Intent.FACTUAL_QA, scores), "Return only the answer.")
            summary = gate.decide(TaskAssessment(Intent.SUMMARIZATION, scores), "Return only one sentence.")
        self.assertTrue(factual.probe)
        self.assertFalse(summary.probe)


if __name__ == "__main__":
    unittest.main()
