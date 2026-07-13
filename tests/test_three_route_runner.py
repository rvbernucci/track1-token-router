import unittest
from time import monotonic
from unittest.mock import patch

from router.core.contracts import (
    AnswerResult,
    AssessmentScores,
    Engine,
    EnginePrediction,
    Intent,
    TaskAssessment,
    TaskEnvelope,
    TokenUsage,
)
from router.core.three_route_runner import ThreeRouteRunner
from router.functiongemma.provider import AssessmentInvocation, FunctionGemmaProviderError
from router.functiongemma.tool_planner_provider import ToolPlannerInvocation
from router.core.tool_planner import ToolPlan
from router.orchestration.game_theory_selector import MinimaxRegretSelector
from router.orchestration.e2b_selective_gate import E2BSelectiveDecision
from router.orchestration.e2b_matrix_gate import E2BMatrixDecision
from router.orchestration.risk_ladder import RiskLadderDecision


ASSESSMENT = TaskAssessment(
    intent=Intent.FACTUAL_QA,
    scores=AssessmentScores(
        deterministic_fit=2,
        reasoning_demand=2,
        knowledge_uncertainty=1,
        generation_demand=2,
        format_complexity=2,
    ),
)


class Provider:
    def assess_with_trace(self, _task):
        return AssessmentInvocation(
            assessment=ASSESSMENT,
            raw_assessment=ASSESSMENT,
            latency_ms=1.0,
            usage=TokenUsage.empty(),
            model="functiongemma",
        )


class BrokenProvider:
    def assess_with_trace(self, _task):
        raise FunctionGemmaProviderError("bad output")


class CalibratedProvider:
    def assess_with_trace(self, _task):
        calibrated = TaskAssessment(
            intent=Intent.SENTIMENT,
            scores=AssessmentScores(5, 3, 0, 4, 2),
        )
        raw = TaskAssessment(
            intent=Intent.SENTIMENT,
            scores=AssessmentScores(5, 2, 0, 2, 2),
        )
        return AssessmentInvocation(
            assessment=calibrated,
            raw_assessment=raw,
            latency_ms=1.0,
            usage=TokenUsage.empty(),
            model="functiongemma",
        )


class RecordingMatrixGate:
    def __init__(self):
        self.assessment = None
        self.prompt = None

    def decide(self, assessment, prompt=None):
        self.assessment = assessment
        self.prompt = prompt
        return E2BMatrixDecision(True, 0.77, 0.75, "probe_e2b")


class RiskPolicy:
    def __init__(self, action="e2b"):
        self.action = action

    def decide(self, *, intent, probability, remaining_ms):
        return RiskLadderDecision(
            self.action, "test", "test_policy", probability, 0.85, 0.9, 46,
        )


class Predictor:
    def __init__(self, e2b=0.2, fireworks=0.9):
        self.probabilities = {Engine.GEMMA_E2B: e2b, Engine.FIREWORKS: fireworks}

    def predict(self, _features, engine):
        return EnginePrediction(
            engine=engine,
            probability_correct=self.probabilities[engine],
            expected_latency_ms=10,
            expected_fireworks_tokens=100 if engine is Engine.FIREWORKS else 0,
            probability_runtime_failure=0.01,
            expected_peak_memory_mb=100,
            model_version="test",
        )

    def uncertainty(self, _prediction):
        return 0.0


class Runner:
    def __init__(self, answer, route, metadata=None):
        self.answer = answer
        self.route = route
        self.metadata = metadata or {}
        self.calls = 0

    def run(self, task):
        self.calls += 1
        return AnswerResult(id=task.id, answer=self.answer, route=self.route, metadata=self.metadata)


class CaptureLogger:
    def __init__(self):
        self.extra = None

    def log_result(self, _task, _result, extra=None):
        self.extra = extra


class BrokenRunner:
    def run(self, _task):
        raise MemoryError("simulated local allocation failure")


class PlannerProvider:
    def __init__(self, plan):
        self.plan = plan
        self.calls = 0

    def plan_with_trace(self, _task):
        self.calls += 1
        return ToolPlannerInvocation(
            plan=self.plan, latency_ms=1.0, usage=TokenUsage.empty(), model="functiongemma-planner",
        )


class SelectivePolicy:
    def __init__(self, *, accepted: bool):
        self.accepted = accepted

    def should_probe(self, _features):
        return E2BSelectiveDecision(True, False, 0.8, None, "probe_e2b_candidate")

    def evaluate(self, _task, answer, _features):
        return E2BSelectiveDecision(
            True,
            self.accepted,
            0.8,
            0.95 if self.accepted else 0.4,
            "selective_local_accept" if self.accepted else "post_probability_below_accept_threshold",
            answer=answer if self.accepted else "",
        )


class ThreeRouteRunnerTests(unittest.TestCase):
    def test_functiongemma_planner_releases_only_recomputed_tool_answer(self):
        planner = PlannerProvider(ToolPlan("safe_calculator", {"ast": {
            "op": "add", "left": {"op": "literal", "value": 2},
            "right": {"op": "literal", "value": 3},
        }}, "high"))
        remote = Runner("remote", "fireworks_direct")
        runner = ThreeRouteRunner(
            assessment_provider=Provider(), predictor=Predictor(),
            selector=MinimaxRegretSelector(e2b_enabled=False),
            e2b_runner=Runner("local", "e2b_local"), fireworks_runner=remote,
            tool_planner_provider=planner,
        )
        task = TaskEnvelope(id="tool", input_text="Calculate 2 + 3. Return only the number.")
        with patch("router.core.three_route_runner.solve_deterministic", return_value=None):
            result = runner.run(task)
        self.assertEqual(result.route, "functiongemma_tool_verified")
        self.assertEqual(result.answer, "5")
        self.assertEqual(result.remote_tokens.total, 0)
        self.assertEqual(planner.calls, 1)
        self.assertEqual(remote.calls, 0)

    def test_functiongemma_planner_rejection_falls_directly_to_fireworks(self):
        planner = PlannerProvider(ToolPlan("none", {}, "low"))
        remote = Runner("remote", "fireworks_direct")
        runner = ThreeRouteRunner(
            assessment_provider=Provider(), predictor=Predictor(),
            selector=MinimaxRegretSelector(e2b_enabled=False),
            e2b_runner=Runner("local", "e2b_local"), fireworks_runner=remote,
            tool_planner_provider=planner,
        )
        task = TaskEnvelope(id="tool", input_text="Calculate 2 + 3. Return only the number.")
        with patch("router.core.three_route_runner.solve_deterministic", return_value=None):
            result = runner.run(task)
        self.assertEqual(result.route, "fireworks_direct")
        self.assertIn("tool_planner_rejected", result.metadata["routing_trace"]["fallback"])
        self.assertEqual(remote.calls, 1)

    def test_safe_runtime_telemetry_is_logged_without_prompt(self):
        logger = CaptureLogger()
        remote = Runner(
            "remote",
            "fireworks_direct",
            metadata={"fireworks_model": "accounts/fireworks/models/kimi-k2p7-code", "latency_fireworks_ms": 17},
        )
        runner = ThreeRouteRunner(
            assessment_provider=Provider(), predictor=Predictor(),
            selector=MinimaxRegretSelector(e2b_enabled=False),
            e2b_runner=Runner("local", "e2b_local"), fireworks_runner=remote, logger=logger,
        )
        runner.run(TaskEnvelope(id="telemetry", input_text="Explain why the sky is blue."))
        self.assertEqual(logger.extra["fireworks_model"], "accounts/fireworks/models/kimi-k2p7-code")
        self.assertEqual(logger.extra["latency_fireworks_ms"], 17)
        self.assertNotIn("prompt", logger.extra)

    def test_matrix_gate_uses_raw_not_calibrated_assessment(self):
        matrix = RecordingMatrixGate()
        remote = Runner("remote", "fireworks_direct")
        runner = ThreeRouteRunner(
            assessment_provider=CalibratedProvider(),
            predictor=Predictor(e2b=0.2, fireworks=0.9),
            selector=MinimaxRegretSelector(e2b_enabled=False),
            e2b_runner=Runner("positive", "e2b_local"),
            fireworks_runner=remote,
            matrix_gate=matrix,
        )

        result = runner.run(TaskEnvelope(id="task", input_text="Classify sentiment as positive or negative."))

        self.assertEqual(matrix.assessment.scores.generation_demand, 2)
        self.assertEqual(matrix.prompt, "Classify sentiment as positive or negative.")
        self.assertEqual(result.route, "e2b_local")
        self.assertEqual(remote.calls, 0)

    def test_disabled_e2b_routes_to_fireworks(self):
        e2b = Runner("local", "e2b_local")
        remote = Runner("remote", "fireworks_direct")
        runner = ThreeRouteRunner(
            assessment_provider=Provider(),
            predictor=Predictor(e2b=0.99, fireworks=0.8),
            selector=MinimaxRegretSelector(e2b_enabled=False),
            e2b_runner=e2b,
            fireworks_runner=remote,
        )
        result = runner.run(TaskEnvelope(id="task", input_text="Explain why the sky is blue."))
        self.assertEqual(result.answer, "remote")
        self.assertEqual(e2b.calls, 0)

    def test_risk_ladder_can_fail_closed_after_matrix_probe(self):
        e2b = Runner("local", "e2b_local")
        remote = Runner("remote", "fireworks_direct")
        runner = ThreeRouteRunner(
            assessment_provider=Provider(), predictor=Predictor(e2b=0.2, fireworks=0.9),
            selector=MinimaxRegretSelector(e2b_enabled=False),
            e2b_runner=e2b, fireworks_runner=remote,
            matrix_gate=RecordingMatrixGate(), risk_ladder=RiskPolicy("fireworks"),
        )
        result = runner.run(TaskEnvelope(id="risk", input_text="Question"))
        self.assertEqual(result.answer, "remote")
        self.assertEqual(e2b.calls, 0)
        self.assertEqual(result.metadata["e2b_matrix"]["reason"], "risk_ladder_fireworks")
        self.assertEqual(result.metadata["risk_ladder"]["action"], "fireworks")

    def test_enabled_high_confidence_e2b_can_answer_locally(self):
        e2b = Runner("Rayleigh scattering.", "e2b_local")
        remote = Runner("remote", "fireworks_direct")
        runner = ThreeRouteRunner(
            assessment_provider=Provider(),
            predictor=Predictor(e2b=0.99, fireworks=0.61),
            selector=MinimaxRegretSelector(e2b_enabled=True),
            e2b_runner=e2b,
            fireworks_runner=remote,
        )
        result = runner.run(TaskEnvelope(id="task", input_text="Explain why the sky is blue."))
        self.assertEqual(result.route, "e2b_local")
        self.assertEqual(remote.calls, 0)

    def test_invalid_e2b_answer_falls_back_to_fireworks(self):
        e2b = Runner("", "e2b_error")
        remote = Runner("remote", "fireworks_direct")
        runner = ThreeRouteRunner(
            assessment_provider=Provider(),
            predictor=Predictor(e2b=0.99, fireworks=0.61),
            selector=MinimaxRegretSelector(e2b_enabled=True),
            e2b_runner=e2b,
            fireworks_runner=remote,
        )
        result = runner.run(TaskEnvelope(id="task", input_text="Explain why the sky is blue."))
        self.assertEqual(result.answer, "remote")
        self.assertIn("e2b_rejected", result.metadata["routing_trace"]["fallback"])

    def test_selective_policy_can_probe_after_preselector_chose_fireworks(self):
        e2b = Runner("positive", "e2b_local")
        remote = Runner("remote", "fireworks_direct")
        runner = ThreeRouteRunner(
            assessment_provider=Provider(),
            predictor=Predictor(e2b=0.2, fireworks=0.9),
            selector=MinimaxRegretSelector(e2b_enabled=False),
            e2b_runner=e2b,
            fireworks_runner=remote,
            selective_policy=SelectivePolicy(accepted=True),
        )

        result = runner.run(TaskEnvelope(id="task", input_text="Classify sentiment."))

        self.assertEqual(result.route, "e2b_local_selective")
        self.assertEqual(remote.calls, 0)
        self.assertEqual(result.metadata["routing_trace"]["decision"]["engine"], "gemma_e2b")

    def test_selective_rejection_falls_closed_to_fireworks(self):
        remote = Runner("remote", "fireworks_direct")
        runner = ThreeRouteRunner(
            assessment_provider=Provider(),
            predictor=Predictor(e2b=0.2, fireworks=0.9),
            selector=MinimaxRegretSelector(e2b_enabled=False),
            e2b_runner=Runner("candidate", "e2b_local"),
            fireworks_runner=remote,
            selective_policy=SelectivePolicy(accepted=False),
        )

        result = runner.run(TaskEnvelope(id="task", input_text="Classify sentiment."))

        self.assertEqual(result.answer, "remote")
        self.assertIn("e2b_selective_rejected", result.metadata["routing_trace"]["fallback"])

    def test_degenerate_e2b_answer_falls_back_to_fireworks(self):
        e2b = Runner(
            "The president of Brazil is elected. president of Brazil and "
            "president of Brazil and president of Brazil and president of Brazil and "
            "president of Brazil",
            "e2b_local",
        )
        remote = Runner("remote", "fireworks_direct")
        runner = ThreeRouteRunner(
            assessment_provider=Provider(),
            predictor=Predictor(e2b=0.99, fireworks=0.61),
            selector=MinimaxRegretSelector(e2b_enabled=True),
            e2b_runner=e2b,
            fireworks_runner=remote,
        )

        result = runner.run(TaskEnvelope(id="task", input_text="Who is the president of Brazil?"))

        self.assertEqual(result.answer, "remote")
        self.assertEqual(
            result.metadata["routing_trace"]["fallback"],
            "e2b_rejected:degenerate_repetition",
        )

    def test_safely_repaired_e2b_answer_avoids_fireworks(self):
        e2b = Runner('```json\n{"answer": 4}\n```', "e2b_local")
        remote = Runner("remote", "fireworks_direct")
        runner = ThreeRouteRunner(
            assessment_provider=Provider(),
            predictor=Predictor(e2b=0.99, fireworks=0.61),
            selector=MinimaxRegretSelector(e2b_enabled=True),
            e2b_runner=e2b,
            fireworks_runner=remote,
        )

        result = runner.run(TaskEnvelope(id="task", input_text="Return only JSON with key answer."))

        self.assertEqual(result.answer, '{"answer": 4}')
        self.assertEqual(result.route, "e2b_local_repaired")
        self.assertEqual(remote.calls, 0)
        self.assertEqual(
            result.metadata["mechanical_repair"]["reason"],
            "safe_repair:markdown_fence_in_strict_format",
        )

    def test_assessment_failure_falls_closed_to_fireworks(self):
        remote = Runner("remote", "fireworks_direct")
        runner = ThreeRouteRunner(
            assessment_provider=BrokenProvider(),
            predictor=Predictor(),
            selector=MinimaxRegretSelector(),
            e2b_runner=Runner("local", "e2b_local"),
            fireworks_runner=remote,
        )
        result = runner.run(TaskEnvelope(id="task", input_text="Anything"))
        self.assertEqual(result.answer, "remote")
        self.assertTrue(result.metadata["routing_trace"]["decision"]["safe_fallback"])

    def test_recoverable_e2b_memory_failure_falls_back_to_fireworks(self):
        remote = Runner("remote", "fireworks_direct")
        runner = ThreeRouteRunner(
            assessment_provider=Provider(),
            predictor=Predictor(e2b=0.99, fireworks=0.61),
            selector=MinimaxRegretSelector(e2b_enabled=True),
            e2b_runner=BrokenRunner(),
            fireworks_runner=remote,
        )
        result = runner.run(TaskEnvelope(id="task", input_text="Explain why the sky is blue."))
        self.assertEqual(result.answer, "remote")
        self.assertEqual(
            result.metadata["routing_trace"]["fallback"],
            "e2b_runtime_failure:MemoryError",
        )

    def test_absolute_run_deadline_reaches_feature_vector(self):
        remote = Runner("remote", "fireworks_direct")
        runner = ThreeRouteRunner(
            assessment_provider=Provider(),
            predictor=Predictor(e2b=0.2, fireworks=0.9),
            selector=MinimaxRegretSelector(),
            e2b_runner=Runner("local", "e2b_local"),
            fireworks_runner=remote,
        )
        runner.set_run_deadline(monotonic() + 60)
        result = runner.run(TaskEnvelope(id="task", input_text="Explain why the sky is blue."))
        trace = result.metadata["routing_trace"]
        features = dict(zip(trace["features"]["names"], trace["features"]["values"], strict=True))
        self.assertLess(features["struct.deadline_remaining_ratio"], 0.11)

    def test_matrix_probe_preserves_remote_fallback_deadline(self):
        matrix = RecordingMatrixGate()
        remote = Runner("remote", "fireworks_direct")
        local = Runner("local", "e2b_local")
        runner = ThreeRouteRunner(
            assessment_provider=Provider(), predictor=Predictor(e2b=0.2, fireworks=0.9),
            selector=MinimaxRegretSelector(e2b_enabled=False),
            e2b_runner=local, fireworks_runner=remote, matrix_gate=matrix,
            e2b_min_remaining_ms=30_000,
        )
        runner.set_run_deadline(monotonic() + 1)
        result = runner.run(TaskEnvelope(id="deadline", input_text="Return a short answer."))
        self.assertEqual(result.answer, "remote")
        self.assertEqual(local.calls, 0)
        self.assertEqual(result.metadata["e2b_matrix"]["reason"], "matrix_deadline_guard")


if __name__ == "__main__":
    unittest.main()
