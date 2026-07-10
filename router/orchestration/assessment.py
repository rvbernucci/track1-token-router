from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from router.core.contracts import (
    AssessmentScores,
    EngineDecision,
    FeatureVector,
    Intent,
    RequestedOutputShape,
    StructuralFeatures,
    TaskAssessment,
    TaskEnvelope,
)
from router.orchestration.solvers import solver_hints_for_assessment, solver_names


DEFAULT_TASK_DEADLINE_MS = 10 * 60 * 1000
INPUT_TOKEN_NORMALIZATION_CEILING = 8192


@dataclass(frozen=True)
class AssessmentParseResult:
    assessment: TaskAssessment | None
    fallback_decision: EngineDecision | None
    error: str = ""

    @property
    def valid(self) -> bool:
        return self.assessment is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "assessment": self.assessment.to_dict() if self.assessment else None,
            "fallback_decision": self.fallback_decision.to_dict() if self.fallback_decision else None,
            "error": self.error,
        }


def parse_task_assessment(raw: str | Mapping[str, Any]) -> AssessmentParseResult:
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(payload, Mapping):
            raise ValueError("TaskAssessment output must be a JSON object.")
        assessment = TaskAssessment.from_mapping(payload)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return AssessmentParseResult(
            assessment=None,
            fallback_decision=EngineDecision.fireworks_safe_fallback("invalid_task_assessment"),
            error=str(exc),
        )
    return AssessmentParseResult(assessment=assessment, fallback_decision=None)


def compute_structural_features(
    task: TaskEnvelope,
    *,
    deadline_remaining_ms: int = DEFAULT_TASK_DEADLINE_MS,
    token_counter: Callable[[str], int] | None = None,
) -> StructuralFeatures:
    count_tokens = token_counter or approximate_token_count
    input_tokens = count_tokens(task.input_text)
    return StructuralFeatures(
        input_tokens=input_tokens,
        requested_output_shape=detect_requested_output_shape(task.input_text),
        deadline_remaining_ms=max(0, int(deadline_remaining_ms)),
    )


def build_feature_vector(
    assessment: TaskAssessment,
    structural: StructuralFeatures,
) -> FeatureVector:
    hints = set(solver_hints_for_assessment(assessment))
    names: list[str] = []
    values: list[float] = []

    for intent in Intent:
        names.append(f"intent.{intent.value}")
        values.append(float(assessment.intent is intent))

    for score_name, score in assessment.scores.to_dict().items():
        names.append(f"score.{score_name}")
        values.append(score / 10.0)

    names.append("struct.input_tokens_log")
    values.append(
        min(
            1.0,
            math.log1p(structural.input_tokens) / math.log1p(INPUT_TOKEN_NORMALIZATION_CEILING),
        )
    )

    for shape in RequestedOutputShape:
        names.append(f"shape.{shape.value}")
        values.append(float(structural.requested_output_shape is shape))

    names.append("struct.deadline_remaining_ratio")
    values.append(min(1.0, structural.deadline_remaining_ms / DEFAULT_TASK_DEADLINE_MS))

    for solver_name in solver_names():
        names.append(f"solver_hint.{solver_name}")
        values.append(float(solver_name in hints))

    return FeatureVector(names=tuple(names), values=tuple(values))


def approximate_token_count(text: str) -> int:
    if not text:
        return 0
    byte_estimate = math.ceil(len(text.encode("utf-8")) / 4)
    lexical_floor = len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))
    return max(1, byte_estimate, lexical_floor)


def detect_requested_output_shape(text: str) -> RequestedOutputShape:
    lowered = text.lower()
    if re.search(r"\b(json|jsonl|json schema|valid json)\b", lowered):
        return RequestedOutputShape.JSON
    if re.search(r"\b(code|function|class|program|script|typescript|javascript|python)\b", lowered):
        return RequestedOutputShape.CODE
    if re.search(r"\b(return|answer|output)\s+(?:only\s+)?(?:the\s+)?(?:number|integer|decimal|numeric)", lowered):
        return RequestedOutputShape.NUMBER
    if re.search(r"\b(yes or no|true or false|boolean)\b", lowered):
        return RequestedOutputShape.BOOLEAN
    if re.search(r"\b(bullet(?:ed)? list|numbered list|list of|array of)\b", lowered):
        return RequestedOutputShape.LIST
    if re.search(r"\b(one word|single word|short answer|return only|nothing else)\b", lowered):
        return RequestedOutputShape.SHORT_TEXT
    return RequestedOutputShape.FREE_TEXT


def assessment_example() -> TaskAssessment:
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
