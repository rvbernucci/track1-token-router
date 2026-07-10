import unittest

from router.core.contracts import Engine, EnginePrediction, FeatureVector
from router.orchestration.game_theory_selector import (
    MinimaxRegretSelector,
    RobustSelectionConfig,
    deterministic_solver_prediction,
)


FEATURES = FeatureVector(names=("x",), values=(0.5,))


def prediction(engine, probability, *, tokens=0, latency=10, failure=0.01, memory=0):
    return EnginePrediction(
        engine=engine,
        probability_correct=probability,
        expected_latency_ms=latency,
        expected_fireworks_tokens=tokens,
        probability_runtime_failure=failure,
        expected_peak_memory_mb=memory,
        model_version="test-v1",
    )


class GameTheorySelectorTests(unittest.TestCase):
    def test_e2b_cannot_be_selected_while_policy_is_disabled(self):
        selector = MinimaxRegretSelector(e2b_enabled=False)
        result = selector.select_with_trace(FEATURES, {
            Engine.DETERMINISTIC: deterministic_solver_prediction(accepted=False),
            Engine.GEMMA_E2B: prediction(Engine.GEMMA_E2B, 0.99),
            Engine.FIREWORKS: prediction(Engine.FIREWORKS, 0.80, tokens=100),
        })
        self.assertEqual(result.decision.engine, Engine.FIREWORKS)
        e2b = next(row for row in result.candidates if row.engine is Engine.GEMMA_E2B)
        self.assertIn("e2b_policy_disabled", e2b.rejection_reasons)

    def test_actual_deterministic_acceptance_dominates_remote_spend(self):
        selector = MinimaxRegretSelector()
        decision = selector.select(FEATURES, {
            Engine.DETERMINISTIC: deterministic_solver_prediction(accepted=True),
            Engine.GEMMA_E2B: prediction(Engine.GEMMA_E2B, 0.2),
            Engine.FIREWORKS: prediction(Engine.FIREWORKS, 0.95, tokens=100),
        })
        self.assertEqual(decision.engine, Engine.DETERMINISTIC)

    def test_uncertainty_can_fail_the_accuracy_gate(self):
        selector = MinimaxRegretSelector(config=RobustSelectionConfig(accuracy_gate=0.70))
        result = selector.select_with_trace(
            FEATURES,
            {
                Engine.DETERMINISTIC: deterministic_solver_prediction(accepted=False),
                Engine.GEMMA_E2B: prediction(Engine.GEMMA_E2B, 0.2),
                Engine.FIREWORKS: prediction(Engine.FIREWORKS, 0.72),
            },
            probability_uncertainty={Engine.FIREWORKS: 0.05},
        )
        self.assertTrue(result.decision.safe_fallback)
        self.assertEqual(result.decision.engine, Engine.FIREWORKS)

    def test_memory_gate_rejects_local_engine(self):
        selector = MinimaxRegretSelector(e2b_enabled=True)
        result = selector.select_with_trace(FEATURES, {
            Engine.GEMMA_E2B: prediction(Engine.GEMMA_E2B, 0.99, memory=4000),
            Engine.FIREWORKS: prediction(Engine.FIREWORKS, 0.80, tokens=100),
        })
        e2b = next(row for row in result.candidates if row.engine is Engine.GEMMA_E2B)
        self.assertIn("peak_memory_above_gate", e2b.rejection_reasons)

    def test_deadline_reserve_is_read_from_the_feature_vector(self):
        selector = MinimaxRegretSelector()
        late = FeatureVector(names=("struct.deadline_remaining_ratio",), values=(0.001,))
        result = selector.select_with_trace(late, {
            Engine.FIREWORKS: prediction(Engine.FIREWORKS, 0.99, latency=1000),
        })
        candidate = result.candidates[0]
        self.assertIn("deadline_reserve_exhausted", candidate.rejection_reasons)
        self.assertTrue(result.decision.safe_fallback)


if __name__ == "__main__":
    unittest.main()
