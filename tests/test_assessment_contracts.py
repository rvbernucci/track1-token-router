import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from router.core.config import RouterConfig
from router.core.contracts import (
    ASSESSMENT_SCHEMA_VERSION,
    ENGINE_OUTCOME_SCHEMA_VERSION,
    FEATURE_SCHEMA_VERSION,
    SUB_INTENT_TAXONOMY_VERSION,
    AssessmentScores,
    Engine,
    EngineDecision,
    EngineOutcomeObservation,
    EnginePrediction,
    FeatureVector,
    Intent,
    RequestedOutputShape,
    RoutingTrace,
    StructuralFeatures,
    SUB_INTENTS_BY_INTENT,
    TaskAssessment,
    TaskEnvelope,
)
from router.core.logging import JsonlRunLogger
from router.core.runner_factory import build_runner
from router.orchestration.assessment import (
    build_feature_vector,
    compute_structural_features,
    detect_requested_output_shape,
    parse_task_assessment,
)
from router.orchestration.solvers import solver_hints_for_assessment, solver_manifest, solver_names
from tests.fake_openai_server import FakeOpenAIServer


def arithmetic_assessment() -> TaskAssessment:
    return TaskAssessment(
        intent=Intent.MATH_REASONING,
        sub_intent="arithmetic",
        scores=AssessmentScores(
            deterministic_fit=10,
            reasoning_demand=2,
            knowledge_uncertainty=0,
            generation_demand=0,
            format_complexity=2,
        ),
    )


class AssessmentContractTests(unittest.TestCase):
    def test_taxonomy_is_versioned_and_has_exactly_eight_track1_intents(self) -> None:
        self.assertEqual(ASSESSMENT_SCHEMA_VERSION, "task-assessment-v1")
        self.assertEqual(SUB_INTENT_TAXONOMY_VERSION, "track1-sub-intents-v1")
        self.assertEqual(len(Intent), 8)
        self.assertEqual(set(SUB_INTENTS_BY_INTENT), set(Intent))
        self.assertTrue(all(SUB_INTENTS_BY_INTENT[intent] for intent in Intent))

    def test_assessment_round_trip_is_deterministic_and_immutable(self) -> None:
        assessment = arithmetic_assessment()
        serialized = assessment.to_json()
        restored = TaskAssessment.from_mapping(json.loads(serialized))

        self.assertEqual(restored, assessment)
        self.assertEqual(restored.to_json(), serialized)
        with self.assertRaises(FrozenInstanceError):
            assessment.sub_intent = "algebra"  # type: ignore[misc]

    def test_scores_reject_bool_float_and_out_of_range_values(self) -> None:
        base = arithmetic_assessment().scores.to_dict()
        for invalid in (True, 1.5, -1, 11):
            payload = dict(base)
            payload["deterministic_fit"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                AssessmentScores.from_mapping(payload)

    def test_assessment_rejects_missing_additional_and_route_fields(self) -> None:
        payload = arithmetic_assessment().to_dict()
        for key in ("engine", "route", "model", "confidence", "answer"):
            injected = dict(payload)
            injected[key] = "fireworks"
            result = parse_task_assessment(injected)
            with self.subTest(key=key):
                self.assertFalse(result.valid)
                self.assertEqual(result.fallback_decision.engine, Engine.FIREWORKS)
                self.assertTrue(result.fallback_decision.safe_fallback)

        missing = dict(payload)
        missing.pop("scores")
        self.assertFalse(parse_task_assessment(missing).valid)

    def test_assessment_rejects_sub_intent_from_another_intent(self) -> None:
        payload = arithmetic_assessment().to_dict()
        payload["sub_intent"] = "python_debug"

        result = parse_task_assessment(payload)

        self.assertFalse(result.valid)
        self.assertEqual(result.fallback_decision.reason, "invalid_task_assessment")

    def test_non_json_and_non_object_fail_closed_to_fireworks(self) -> None:
        for raw in ("not json", "[]", '```json\n{"intent":"factual_qa"}\n```'):
            result = parse_task_assessment(raw)
            with self.subTest(raw=raw):
                self.assertFalse(result.valid)
                self.assertEqual(result.fallback_decision.feasible_engines, (Engine.FIREWORKS,))


class FeatureContractTests(unittest.TestCase):
    def test_structural_features_are_computed_by_code(self) -> None:
        task = TaskEnvelope(input_text="Return only the number: 17")

        features = compute_structural_features(
            task,
            deadline_remaining_ms=1234,
            token_counter=lambda _text: 7,
        )

        self.assertEqual(features.input_tokens, 7)
        self.assertEqual(features.requested_output_shape, RequestedOutputShape.NUMBER)
        self.assertEqual(features.deadline_remaining_ms, 1234)

    def test_requested_output_shape_detection_is_mechanical(self) -> None:
        cases = {
            "Return valid JSON with a name field": RequestedOutputShape.JSON,
            "Write a Python function that adds two values": RequestedOutputShape.CODE,
            "Answer yes or no": RequestedOutputShape.BOOLEAN,
            "Provide a numbered list of cities": RequestedOutputShape.LIST,
            "Return only Ottawa and nothing else": RequestedOutputShape.SHORT_TEXT,
            "Explain the result": RequestedOutputShape.FREE_TEXT,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(detect_requested_output_shape(text), expected)

    def test_feature_vector_is_canonical_normalized_and_round_trips(self) -> None:
        structural = StructuralFeatures(
            input_tokens=128,
            requested_output_shape=RequestedOutputShape.NUMBER,
            deadline_remaining_ms=300_000,
        )

        vector = build_feature_vector(arithmetic_assessment(), structural)
        restored = FeatureVector.from_mapping(json.loads(vector.to_json()))
        feature_map = dict(zip(vector.names, vector.values, strict=True))

        self.assertEqual(vector.schema_version, FEATURE_SCHEMA_VERSION)
        self.assertEqual(restored, vector)
        self.assertEqual(feature_map["intent.math_reasoning"], 1.0)
        self.assertEqual(feature_map["score.deterministic_fit"], 1.0)
        self.assertEqual(feature_map["shape.number"], 1.0)
        self.assertEqual(feature_map["struct.deadline_remaining_ratio"], 0.5)
        self.assertEqual(feature_map["solver_hint.arithmetic"], 1.0)
        self.assertTrue(all(0.0 <= value <= 1.0 for value in vector.values))

    def test_solver_hints_come_from_the_registered_manifest(self) -> None:
        hints = solver_hints_for_assessment(arithmetic_assessment())
        manifest_names = tuple(item["name"] for item in solver_manifest())

        self.assertEqual(hints, ("arithmetic",))
        self.assertEqual(manifest_names, solver_names())
        self.assertEqual(len(set(manifest_names)), len(manifest_names))


class DecisionAndOutcomeContractTests(unittest.TestCase):
    def test_engine_decision_round_trip_and_invariants(self) -> None:
        decision = EngineDecision(
            engine=Engine.DETERMINISTIC,
            reason="minimum_regret",
            feasible_engines=(Engine.DETERMINISTIC, Engine.FIREWORKS),
            probability_correct=0.99,
            worst_case_regret=0.01,
            solver_hint="arithmetic",
        )

        restored = EngineDecision.from_mapping(decision.to_dict())

        self.assertEqual(restored, decision)
        with self.assertRaises(ValueError):
            EngineDecision(engine=Engine.GEMMA_E2B, reason="bad", feasible_engines=(Engine.FIREWORKS,))

    def test_engine_outcome_round_trip_and_local_zero_token_invariant(self) -> None:
        observation = EngineOutcomeObservation(
            task_id="task-1",
            engine=Engine.GEMMA_E2B,
            correct=True,
            latency_ms=90,
            fireworks_prompt_tokens=0,
            fireworks_completion_tokens=0,
            runtime_failure=False,
            peak_memory_mb=1800.5,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            engine_version="gemma-e2b-q4-v1",
            model_id="litert-community/gemma-4-E2B-it-litert-lm",
        )

        restored = EngineOutcomeObservation.from_mapping(observation.to_dict())

        self.assertEqual(restored, observation)
        self.assertEqual(restored.schema_version, ENGINE_OUTCOME_SCHEMA_VERSION)
        with self.assertRaises(ValueError):
            EngineOutcomeObservation(
                task_id="bad",
                engine=Engine.DETERMINISTIC,
                correct=True,
                latency_ms=1,
                fireworks_prompt_tokens=1,
                fireworks_completion_tokens=0,
                runtime_failure=False,
                peak_memory_mb=1,
                feature_schema_version=FEATURE_SCHEMA_VERSION,
                engine_version="solver-v1",
            )

    def test_routing_trace_round_trip(self) -> None:
        assessment = arithmetic_assessment()
        features = build_feature_vector(
            assessment,
            StructuralFeatures(10, RequestedOutputShape.NUMBER, 500_000),
        )
        prediction = EnginePrediction(
            engine=Engine.FIREWORKS,
            probability_correct=0.98,
            expected_latency_ms=500,
            expected_fireworks_tokens=80,
            probability_runtime_failure=0.01,
            expected_peak_memory_mb=100,
            model_version="regression-v1",
        )
        decision = EngineDecision.fireworks_safe_fallback("test")
        trace = RoutingTrace("task-1", assessment, features, (prediction,), decision, fallback="test")

        restored = RoutingTrace.from_mapping(json.loads(trace.to_json()))

        self.assertEqual(restored, trace)


class Sprint45FactoryTests(unittest.TestCase):
    def test_three_route_starts_in_fireworks_safe_mode_with_v1_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeOpenAIServer(response_text="chlorophyll") as server:
            with patched_env(
                ROUTER_MODE="three_route",
                FIREWORKS_BASE_URL=server.url,
                FIREWORKS_MODEL="minimax-m3",
                FIREWORKS_API_KEY="test-key",
                FIREWORKS_MAX_RETRIES="0",
                ROUTER_LOG_PATH=str(Path(tmp) / "run.jsonl"),
            ):
                config = RouterConfig.from_env()
                runner = build_runner(config, JsonlRunLogger(config.log_path))
                result = runner.run(TaskEnvelope(id="safe", input_text="Name the pigment used in photosynthesis."))

        trace = result.metadata["routing_trace"]
        self.assertEqual(result.route, "fireworks_direct")
        self.assertEqual(trace["schema_version"], "routing-trace-v1")
        self.assertEqual(trace["decision"]["engine"], "fireworks")
        self.assertTrue(trace["decision"]["safe_fallback"])
        self.assertEqual(len(server.requests), 1)

    def test_retired_cascade_modes_are_disabled_by_default(self) -> None:
        with patched_env(ROUTER_MODE="cascade", ENABLE_LEGACY_CASCADE_MODES=None):
            config = RouterConfig.from_env()
            with self.assertRaisesRegex(ValueError, "retired"):
                build_runner(config, JsonlRunLogger(config.log_path))

    def test_three_route_preserves_official_input_output_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "output" / "results.json"
            log_path = Path(tmp) / "run.jsonl"
            env = {
                **os.environ,
                "ROUTER_MODE": "three_route",
                "FIREWORKS_MODEL": "minimax-m3",
                "ALLOWED_MODELS": "minimax-m3",
                "FIREWORKS_API_KEY": "test-key",
                "FIREWORKS_MAX_RETRIES": "0",
                "ROUTER_LOG_PATH": str(log_path),
            }
            with FakeOpenAIServer(responses=["Local verification reduces remote token spend.", "42"]) as server:
                env["FIREWORKS_BASE_URL"] = server.url
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "router",
                        "submit-track1",
                        "--input",
                        "fixtures/official/lablab_track1_tasks.json",
                        "--output",
                        str(output_path),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    env=env,
                )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            log_records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(
            payload,
            [
                {"task_id": "t1", "answer": "Local verification reduces remote token spend."},
                {"task_id": "t2", "answer": "42"},
            ],
        )
        self.assertEqual(len(log_records), 2)
        self.assertTrue(
            all(
                record["extra"]["routing_trace"]["schema_version"] == "routing-trace-v1"
                for record in log_records
            )
        )


class SchemaArtifactTests(unittest.TestCase):
    def test_schema_artifacts_match_code_enums_and_fail_closed(self) -> None:
        assessment_schema = json.loads(Path("schemas/task-assessment-v1.schema.json").read_text(encoding="utf-8"))
        feature_schema = json.loads(Path("schemas/feature-vector-v1.schema.json").read_text(encoding="utf-8"))
        outcome_schema = json.loads(Path("schemas/engine-outcome-v1.schema.json").read_text(encoding="utf-8"))
        trace_schema = json.loads(Path("schemas/routing-trace-v1.schema.json").read_text(encoding="utf-8"))

        self.assertFalse(assessment_schema["additionalProperties"])
        self.assertEqual(set(assessment_schema["properties"]["intent"]["enum"]), {intent.value for intent in Intent})
        schema_sub_intents = {
            clause["if"]["properties"]["intent"]["const"]: tuple(
                clause["then"]["properties"]["sub_intent"]["enum"]
            )
            for clause in assessment_schema["allOf"]
        }
        self.assertEqual(
            schema_sub_intents,
            {intent.value: sub_intents for intent, sub_intents in SUB_INTENTS_BY_INTENT.items()},
        )
        self.assertEqual(
            set(assessment_schema["properties"]["scores"]["properties"]),
            set(arithmetic_assessment().scores.to_dict()),
        )
        self.assertFalse(feature_schema["additionalProperties"])
        self.assertEqual(feature_schema["properties"]["schema_version"]["const"], FEATURE_SCHEMA_VERSION)
        self.assertEqual(set(feature_schema["properties"]), {"schema_version", "names", "values"})
        self.assertEqual(outcome_schema["properties"]["schema_version"]["const"], ENGINE_OUTCOME_SCHEMA_VERSION)
        outcome = EngineOutcomeObservation(
            task_id="schema",
            engine=Engine.DETERMINISTIC,
            correct=True,
            latency_ms=1,
            fireworks_prompt_tokens=0,
            fireworks_completion_tokens=0,
            runtime_failure=False,
            peak_memory_mb=1,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            engine_version="solver-v1",
        )
        self.assertEqual(set(outcome_schema["properties"]), set(outcome.to_dict()))
        self.assertEqual(set(outcome_schema["required"]), set(outcome.to_dict()))
        self.assertTrue(outcome_schema["allOf"])
        self.assertEqual(trace_schema["properties"]["schema_version"]["const"], "routing-trace-v1")
        safe_decision = EngineDecision.fireworks_safe_fallback("schema")
        self.assertFalse(trace_schema["properties"]["decision"]["additionalProperties"])
        self.assertEqual(
            set(trace_schema["properties"]["decision"]["properties"]),
            set(safe_decision.to_dict()),
        )
        prediction = EnginePrediction(
            engine=Engine.FIREWORKS,
            probability_correct=1,
            expected_latency_ms=1,
            expected_fireworks_tokens=1,
            probability_runtime_failure=0,
            expected_peak_memory_mb=1,
            model_version="schema-v1",
        )
        prediction_schema = trace_schema["properties"]["predictions"]["items"]
        self.assertFalse(prediction_schema["additionalProperties"])
        self.assertEqual(set(prediction_schema["properties"]), set(prediction.to_dict()))


class patched_env:
    def __init__(self, **values: str | None) -> None:
        self.values = values
        self.previous: dict[str, str | None] = {}

    def __enter__(self) -> None:
        for key, value in self.values.items():
            self.previous[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def __exit__(self, *_exc: object) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
