from __future__ import annotations

from typing import Mapping, Protocol, Sequence

from router.core.contracts import (
    AnswerResult,
    Engine,
    EngineDecision,
    EnginePrediction,
    FeatureVector,
    TaskAssessment,
    TaskEnvelope,
)


class TaskRunner(Protocol):
    def run(self, task: TaskEnvelope) -> AnswerResult:
        ...


class AssessmentProvider(Protocol):
    def assess(self, task: TaskEnvelope) -> TaskAssessment:
        ...


class OutcomePredictor(Protocol):
    def predict(self, features: FeatureVector, engine: Engine) -> EnginePrediction:
        ...


class EngineSelector(Protocol):
    def select(
        self,
        features: FeatureVector,
        predictions: Mapping[Engine, EnginePrediction],
    ) -> EngineDecision:
        ...


class EngineExecutor(Protocol):
    def execute(
        self,
        task: TaskEnvelope,
        decision: EngineDecision,
        ranked_predictions: Sequence[EnginePrediction],
    ) -> AnswerResult:
        ...
