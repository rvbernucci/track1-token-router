from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


ASSESSMENT_SCHEMA_VERSION = "task-assessment-v1"
FEATURE_SCHEMA_VERSION = "feature-vector-v1"
ENGINE_OUTCOME_SCHEMA_VERSION = "engine-outcome-v1"
SUB_INTENT_TAXONOMY_VERSION = "track1-sub-intents-v1"


class Intent(str, Enum):
    FACTUAL_QA = "factual_qa"
    MATH_REASONING = "math_reasoning"
    SENTIMENT = "sentiment"
    SUMMARIZATION = "summarization"
    NER = "ner"
    CODE_DEBUGGING = "code_debugging"
    LOGIC_PUZZLE = "logic_puzzle"
    CODE_GENERATION = "code_generation"


SUB_INTENTS_BY_INTENT: dict[Intent, tuple[str, ...]] = {
    Intent.FACTUAL_QA: ("stable_fact", "current_fact", "context_qa", "open_domain_fact"),
    Intent.MATH_REASONING: (
        "arithmetic",
        "percent_fee_math",
        "proportional_rate",
        "numeric_compare",
        "algebra",
        "geometry",
        "probability",
        "statistics",
        "other_math",
    ),
    Intent.SENTIMENT: ("polarity", "aspect_sentiment"),
    Intent.SUMMARIZATION: ("constrained_summary", "extractive_summary", "abstractive_summary"),
    Intent.NER: ("entity_extract", "typed_entity_extract"),
    Intent.CODE_DEBUGGING: ("python_debug", "javascript_debug", "typescript_debug", "other_code_debug"),
    Intent.LOGIC_PUZZLE: ("ordering", "deduction", "modus_ponens", "modus_tollens", "other_logic"),
    Intent.CODE_GENERATION: (
        "python_generation",
        "javascript_generation",
        "typescript_generation",
        "other_code_generation",
    ),
}


class Engine(str, Enum):
    DETERMINISTIC = "deterministic"
    GEMMA_E2B = "gemma_e2b"
    FIREWORKS = "fireworks"


class RequestedOutputShape(str, Enum):
    FREE_TEXT = "free_text"
    SHORT_TEXT = "short_text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    JSON = "json"
    CODE = "code"
    LIST = "list"


@dataclass(frozen=True)
class AssessmentScores:
    deterministic_fit: int
    reasoning_demand: int
    knowledge_uncertainty: int
    generation_demand: int
    format_complexity: int

    def __post_init__(self) -> None:
        for name, value in self.to_dict().items():
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10:
                raise ValueError(f"AssessmentScores.{name} must be an integer in [0, 10].")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "AssessmentScores":
        expected = {
            "deterministic_fit",
            "reasoning_demand",
            "knowledge_uncertainty",
            "generation_demand",
            "format_complexity",
        }
        _require_exact_keys(payload, expected, "AssessmentScores")
        return cls(**{name: payload[name] for name in expected})

    def to_dict(self) -> dict[str, int]:
        return {
            "deterministic_fit": self.deterministic_fit,
            "reasoning_demand": self.reasoning_demand,
            "knowledge_uncertainty": self.knowledge_uncertainty,
            "generation_demand": self.generation_demand,
            "format_complexity": self.format_complexity,
        }


@dataclass(frozen=True)
class TaskAssessment:
    intent: Intent
    scores: AssessmentScores
    sub_intent: str | None = None
    schema_version: str = ASSESSMENT_SCHEMA_VERSION
    taxonomy_version: str = SUB_INTENT_TAXONOMY_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.intent, Intent):
            raise ValueError("TaskAssessment.intent must be an Intent.")
        if self.sub_intent is not None and (
            not isinstance(self.sub_intent, str) or self.sub_intent not in SUB_INTENTS_BY_INTENT[self.intent]
        ):
            raise ValueError(f"Invalid sub_intent {self.sub_intent!r} for intent {self.intent.value!r}.")
        if self.schema_version != ASSESSMENT_SCHEMA_VERSION:
            raise ValueError(f"Unsupported assessment schema: {self.schema_version!r}.")
        if self.taxonomy_version != SUB_INTENT_TAXONOMY_VERSION:
            raise ValueError(f"Unsupported sub-intent taxonomy: {self.taxonomy_version!r}.")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "TaskAssessment":
        expected = {"intent", "scores"}
        if "sub_intent" in payload:
            expected.add("sub_intent")
        _require_exact_keys(payload, expected, "TaskAssessment")
        try:
            intent = Intent(payload["intent"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Unknown assessment intent: {payload.get('intent')!r}.") from exc
        scores = payload["scores"]
        if not isinstance(scores, Mapping):
            raise ValueError("TaskAssessment.scores must be an object.")
        return cls(
            intent=intent,
            scores=AssessmentScores.from_mapping(scores),
            sub_intent=(
                _required_str(payload["sub_intent"], "TaskAssessment.sub_intent")
                if "sub_intent" in payload
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "intent": self.intent.value,
            "scores": self.scores.to_dict(),
        }
        if self.sub_intent is not None:
            payload["sub_intent"] = self.sub_intent
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class StructuralFeatures:
    input_tokens: int
    requested_output_shape: RequestedOutputShape
    deadline_remaining_ms: int

    def __post_init__(self) -> None:
        if isinstance(self.input_tokens, bool) or not isinstance(self.input_tokens, int) or self.input_tokens < 0:
            raise ValueError("StructuralFeatures.input_tokens must be a non-negative integer.")
        if not isinstance(self.requested_output_shape, RequestedOutputShape):
            raise ValueError("StructuralFeatures.requested_output_shape must be a RequestedOutputShape.")
        if (
            isinstance(self.deadline_remaining_ms, bool)
            or not isinstance(self.deadline_remaining_ms, int)
            or self.deadline_remaining_ms < 0
        ):
            raise ValueError("StructuralFeatures.deadline_remaining_ms must be a non-negative integer.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "requested_output_shape": self.requested_output_shape.value,
            "deadline_remaining_ms": self.deadline_remaining_ms,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "StructuralFeatures":
        _require_exact_keys(
            payload,
            {"input_tokens", "requested_output_shape", "deadline_remaining_ms"},
            "StructuralFeatures",
        )
        try:
            shape = RequestedOutputShape(payload["requested_output_shape"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Unknown requested output shape: {payload.get('requested_output_shape')!r}.") from exc
        return cls(
            input_tokens=payload["input_tokens"],
            requested_output_shape=shape,
            deadline_remaining_ms=payload["deadline_remaining_ms"],
        )


@dataclass(frozen=True)
class FeatureVector:
    names: tuple[str, ...]
    values: tuple[float, ...]
    schema_version: str = FEATURE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != FEATURE_SCHEMA_VERSION:
            raise ValueError(f"Unsupported feature schema: {self.schema_version!r}.")
        if not self.names or len(self.names) != len(self.values) or len(set(self.names)) != len(self.names):
            raise ValueError("FeatureVector names and values must be non-empty, aligned and unique.")
        if any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            or not 0 <= value <= 1
            for value in self.values
        ):
            raise ValueError("FeatureVector values must be finite numeric values in [0, 1].")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "names": list(self.names),
            "values": list(self.values),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "FeatureVector":
        _require_exact_keys(payload, {"schema_version", "names", "values"}, "FeatureVector")
        names = payload["names"]
        values = payload["values"]
        if not isinstance(names, list) or not isinstance(values, list):
            raise ValueError("FeatureVector.names and values must be arrays.")
        return cls(
            names=tuple(_required_str(name, "FeatureVector.names[]") for name in names),
            values=tuple(values),
            schema_version=_required_str(payload["schema_version"], "FeatureVector.schema_version"),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class EnginePrediction:
    engine: Engine
    probability_correct: float
    expected_latency_ms: float
    expected_fireworks_tokens: float
    probability_runtime_failure: float
    expected_peak_memory_mb: float
    model_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.engine, Engine):
            raise ValueError("EnginePrediction.engine must be an Engine.")
        for name in ("probability_correct", "probability_runtime_failure"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 <= value <= 1
            ):
                raise ValueError(f"EnginePrediction.{name} must be in [0, 1].")
        for name in ("expected_latency_ms", "expected_fireworks_tokens", "expected_peak_memory_mb"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"EnginePrediction.{name} must be non-negative.")
        if not isinstance(self.model_version, str) or not self.model_version:
            raise ValueError("EnginePrediction.model_version is required.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine.value,
            "probability_correct": self.probability_correct,
            "expected_latency_ms": self.expected_latency_ms,
            "expected_fireworks_tokens": self.expected_fireworks_tokens,
            "probability_runtime_failure": self.probability_runtime_failure,
            "expected_peak_memory_mb": self.expected_peak_memory_mb,
            "model_version": self.model_version,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "EnginePrediction":
        expected = {
            "engine",
            "probability_correct",
            "expected_latency_ms",
            "expected_fireworks_tokens",
            "probability_runtime_failure",
            "expected_peak_memory_mb",
            "model_version",
        }
        _require_exact_keys(payload, expected, "EnginePrediction")
        try:
            engine = Engine(payload["engine"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Unknown engine: {payload.get('engine')!r}.") from exc
        return cls(
            engine=engine,
            probability_correct=payload["probability_correct"],
            expected_latency_ms=payload["expected_latency_ms"],
            expected_fireworks_tokens=payload["expected_fireworks_tokens"],
            probability_runtime_failure=payload["probability_runtime_failure"],
            expected_peak_memory_mb=payload["expected_peak_memory_mb"],
            model_version=_required_str(payload["model_version"], "EnginePrediction.model_version"),
        )


@dataclass(frozen=True)
class EngineDecision:
    engine: Engine
    reason: str
    feasible_engines: tuple[Engine, ...]
    probability_correct: float | None = None
    worst_case_regret: float | None = None
    solver_hint: str | None = None
    safe_fallback: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.engine, Engine):
            raise ValueError("EngineDecision.engine must be an Engine.")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("EngineDecision.reason is required.")
        if any(not isinstance(engine, Engine) for engine in self.feasible_engines):
            raise ValueError("EngineDecision.feasible_engines must contain only Engine values.")
        if self.engine not in self.feasible_engines:
            raise ValueError("EngineDecision.engine must be included in feasible_engines.")
        if self.probability_correct is not None and (
            isinstance(self.probability_correct, bool)
            or not isinstance(self.probability_correct, (int, float))
            or not math.isfinite(self.probability_correct)
            or not 0 <= self.probability_correct <= 1
        ):
            raise ValueError("EngineDecision.probability_correct must be numeric and in [0, 1].")
        if self.worst_case_regret is not None and (
            isinstance(self.worst_case_regret, bool)
            or not isinstance(self.worst_case_regret, (int, float))
            or not math.isfinite(self.worst_case_regret)
            or self.worst_case_regret < 0
        ):
            raise ValueError("EngineDecision.worst_case_regret must be numeric and non-negative.")
        if not isinstance(self.safe_fallback, bool):
            raise ValueError("EngineDecision.safe_fallback must be a boolean.")

    @classmethod
    def fireworks_safe_fallback(cls, reason: str) -> "EngineDecision":
        return cls(
            engine=Engine.FIREWORKS,
            reason=reason,
            feasible_engines=(Engine.FIREWORKS,),
            safe_fallback=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine.value,
            "reason": self.reason,
            "feasible_engines": [engine.value for engine in self.feasible_engines],
            "probability_correct": self.probability_correct,
            "worst_case_regret": self.worst_case_regret,
            "solver_hint": self.solver_hint,
            "safe_fallback": self.safe_fallback,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "EngineDecision":
        expected = {
            "engine",
            "reason",
            "feasible_engines",
            "probability_correct",
            "worst_case_regret",
            "solver_hint",
            "safe_fallback",
        }
        _require_exact_keys(payload, expected, "EngineDecision")
        feasible = payload["feasible_engines"]
        if not isinstance(feasible, list):
            raise ValueError("EngineDecision.feasible_engines must be an array.")
        try:
            return cls(
                engine=Engine(payload["engine"]),
                reason=_required_str(payload["reason"], "EngineDecision.reason"),
                feasible_engines=tuple(Engine(item) for item in feasible),
                probability_correct=payload["probability_correct"],
                worst_case_regret=payload["worst_case_regret"],
                solver_hint=_strict_optional_str(payload["solver_hint"], "EngineDecision.solver_hint"),
                safe_fallback=payload["safe_fallback"],
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid EngineDecision: {exc}") from exc


@dataclass(frozen=True)
class EngineOutcomeObservation:
    task_id: str
    engine: Engine
    correct: bool
    latency_ms: int
    fireworks_prompt_tokens: int
    fireworks_completion_tokens: int
    runtime_failure: bool
    peak_memory_mb: float
    feature_schema_version: str
    engine_version: str
    model_id: str | None = None
    schema_version: str = ENGINE_OUTCOME_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not self.task_id:
            raise ValueError("EngineOutcomeObservation.task_id is required and must be a string.")
        if not isinstance(self.engine_version, str) or not self.engine_version:
            raise ValueError("EngineOutcomeObservation task_id and engine_version are required.")
        if self.model_id is not None and not isinstance(self.model_id, str):
            raise ValueError("EngineOutcomeObservation.model_id must be a string or null.")
        if not isinstance(self.engine, Engine):
            raise ValueError("EngineOutcomeObservation.engine must be an Engine.")
        if not isinstance(self.correct, bool) or not isinstance(self.runtime_failure, bool):
            raise ValueError("EngineOutcomeObservation correctness and failure must be booleans.")
        if self.correct and self.runtime_failure:
            raise ValueError("A runtime failure cannot be marked correct.")
        for name in ("latency_ms", "fireworks_prompt_tokens", "fireworks_completion_tokens"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"EngineOutcomeObservation.{name} must be a non-negative integer.")
        if (
            isinstance(self.peak_memory_mb, bool)
            or not isinstance(self.peak_memory_mb, (int, float))
            or not math.isfinite(self.peak_memory_mb)
            or self.peak_memory_mb < 0
        ):
            raise ValueError("EngineOutcomeObservation.peak_memory_mb must be non-negative.")
        if self.feature_schema_version != FEATURE_SCHEMA_VERSION:
            raise ValueError(f"Unsupported feature schema: {self.feature_schema_version!r}.")
        if self.schema_version != ENGINE_OUTCOME_SCHEMA_VERSION:
            raise ValueError(f"Unsupported outcome schema: {self.schema_version!r}.")
        if self.engine is not Engine.FIREWORKS and self.fireworks_total_tokens != 0:
            raise ValueError("Local engine observations must record zero Fireworks tokens.")

    @property
    def fireworks_total_tokens(self) -> int:
        return self.fireworks_prompt_tokens + self.fireworks_completion_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "engine": self.engine.value,
            "correct": self.correct,
            "latency_ms": self.latency_ms,
            "fireworks_prompt_tokens": self.fireworks_prompt_tokens,
            "fireworks_completion_tokens": self.fireworks_completion_tokens,
            "runtime_failure": self.runtime_failure,
            "peak_memory_mb": self.peak_memory_mb,
            "feature_schema_version": self.feature_schema_version,
            "engine_version": self.engine_version,
            "model_id": self.model_id,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "EngineOutcomeObservation":
        expected = {
            "schema_version",
            "task_id",
            "engine",
            "correct",
            "latency_ms",
            "fireworks_prompt_tokens",
            "fireworks_completion_tokens",
            "runtime_failure",
            "peak_memory_mb",
            "feature_schema_version",
            "engine_version",
            "model_id",
        }
        _require_exact_keys(payload, expected, "EngineOutcomeObservation")
        try:
            engine = Engine(payload["engine"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Unknown engine: {payload.get('engine')!r}.") from exc
        return cls(
            schema_version=_required_str(payload["schema_version"], "EngineOutcomeObservation.schema_version"),
            task_id=_required_str(payload["task_id"], "EngineOutcomeObservation.task_id"),
            engine=engine,
            correct=payload["correct"],
            latency_ms=payload["latency_ms"],
            fireworks_prompt_tokens=payload["fireworks_prompt_tokens"],
            fireworks_completion_tokens=payload["fireworks_completion_tokens"],
            runtime_failure=payload["runtime_failure"],
            peak_memory_mb=payload["peak_memory_mb"],
            feature_schema_version=_required_str(
                payload["feature_schema_version"], "EngineOutcomeObservation.feature_schema_version"
            ),
            engine_version=_required_str(payload["engine_version"], "EngineOutcomeObservation.engine_version"),
            model_id=_strict_optional_str(payload["model_id"], "EngineOutcomeObservation.model_id"),
        )


@dataclass(frozen=True)
class RoutingTrace:
    task_id: str | None
    assessment: TaskAssessment | None
    features: FeatureVector | None
    predictions: tuple[EnginePrediction, ...]
    decision: EngineDecision
    fallback: str | None = None
    schema_version: str = "routing-trace-v1"

    def __post_init__(self) -> None:
        if self.schema_version != "routing-trace-v1":
            raise ValueError(f"Unsupported routing trace schema: {self.schema_version!r}.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "assessment": self.assessment.to_dict() if self.assessment else None,
            "features": self.features.to_dict() if self.features else None,
            "predictions": [prediction.to_dict() for prediction in self.predictions],
            "decision": self.decision.to_dict(),
            "fallback": self.fallback,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RoutingTrace":
        expected = {"schema_version", "task_id", "assessment", "features", "predictions", "decision", "fallback"}
        _require_exact_keys(payload, expected, "RoutingTrace")
        assessment_payload = payload["assessment"]
        feature_payload = payload["features"]
        prediction_payload = payload["predictions"]
        decision_payload = payload["decision"]
        if assessment_payload is not None and not isinstance(assessment_payload, Mapping):
            raise ValueError("RoutingTrace.assessment must be an object or null.")
        if feature_payload is not None and not isinstance(feature_payload, Mapping):
            raise ValueError("RoutingTrace.features must be an object or null.")
        if not isinstance(prediction_payload, list):
            raise ValueError("RoutingTrace.predictions must be an array.")
        if any(not isinstance(item, Mapping) for item in prediction_payload):
            raise ValueError("RoutingTrace.predictions entries must be objects.")
        if not isinstance(decision_payload, Mapping):
            raise ValueError("RoutingTrace.decision must be an object.")
        return cls(
            schema_version=_required_str(payload["schema_version"], "RoutingTrace.schema_version"),
            task_id=_strict_optional_str(payload["task_id"], "RoutingTrace.task_id"),
            assessment=TaskAssessment.from_mapping(assessment_payload) if assessment_payload is not None else None,
            features=FeatureVector.from_mapping(feature_payload) if feature_payload is not None else None,
            predictions=tuple(EnginePrediction.from_mapping(item) for item in prediction_payload),
            decision=EngineDecision.from_mapping(decision_payload),
            fallback=_strict_optional_str(payload["fallback"], "RoutingTrace.fallback"),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class FileAttachment:
    name: str
    path: str
    mime_type: str | None = None

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "FileAttachment":
        return cls(
            name=str(payload.get("name") or payload.get("filename") or ""),
            path=str(payload.get("path") or ""),
            mime_type=payload.get("mime_type") or payload.get("mime"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "mime_type": self.mime_type,
        }


@dataclass(frozen=True)
class TaskEnvelope:
    input_text: str
    id: str | None = None
    files: list[FileAttachment] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "TaskEnvelope":
        input_text = _coerce_input_text(payload)
        files_payload = payload.get("files") or []
        if not isinstance(files_payload, list):
            raise ValueError("TaskEnvelope.files must be a list.")
        metadata = payload.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ValueError("TaskEnvelope.metadata must be an object.")
        return cls(
            id=_optional_str(payload.get("id")),
            input_text=input_text,
            files=[
                FileAttachment.from_mapping(item)
                for item in files_payload
                if isinstance(item, dict)
            ],
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "input_text": self.input_text,
            "files": [file.to_dict() for file in self.files],
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class TokenUsage:
    prompt: int = 0
    completion: int = 0
    total: int = 0

    @classmethod
    def empty(cls) -> "TokenUsage":
        return cls()

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt": self.prompt,
            "completion": self.completion,
            "total": self.total,
        }


@dataclass(frozen=True)
class RouteDecision:
    route: str
    decision: str
    reason: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "route": self.route,
            "decision": self.decision,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class AnswerResult:
    answer: str
    route: str
    id: str | None = None
    remote_tokens: TokenUsage = field(default_factory=TokenUsage.empty)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "answer": self.answer,
            "route": self.route,
            "remote_tokens": self.remote_tokens.to_dict(),
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


def _coerce_input_text(payload: dict[str, Any]) -> str:
    for key in ("input_text", "question", "prompt", "input", "text"):
        value = payload.get(key)
        if value is not None:
            if isinstance(value, str):
                return value
            return json.dumps(value, ensure_ascii=False)
    raise ValueError("TaskEnvelope requires one of: input_text, question, prompt, input, text.")


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _required_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value


def _strict_optional_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or null.")
    return value


def _require_exact_keys(payload: Mapping[str, Any], expected: set[str], contract: str) -> None:
    actual = set(payload)
    if actual == expected:
        return
    missing = sorted(expected - actual)
    additional = sorted(actual - expected)
    details: list[str] = []
    if missing:
        details.append(f"missing={missing}")
    if additional:
        details.append(f"additional={additional}")
    raise ValueError(f"{contract} fields do not match the schema ({', '.join(details)}).")
