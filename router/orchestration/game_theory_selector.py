from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from router.core.contracts import Engine, EngineDecision, EnginePrediction, FeatureVector


@dataclass(frozen=True)
class RobustSelectionConfig:
    accuracy_gate: float = 0.60
    max_runtime_failure: float = 0.15
    max_peak_memory_mb: float = 3584.0
    deadline_reserve_ms: float = 500.0
    accuracy_reward: float = 100.0
    remote_token_penalty: float = 0.02
    latency_penalty: float = 0.001
    failure_penalty: float = 30.0
    resource_uncertainty_ratio: float = 0.20

    def __post_init__(self) -> None:
        for name in ("accuracy_gate", "max_runtime_failure", "resource_uncertainty_ratio"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be in [0, 1].")
        if self.max_peak_memory_mb <= 0 or self.deadline_reserve_ms < 0:
            raise ValueError("Memory must be positive and deadline reserve non-negative.")


@dataclass(frozen=True)
class RobustCandidate:
    engine: Engine
    feasible: bool
    rejection_reasons: tuple[str, ...]
    probability_low: float
    probability_high: float
    utility_low: float
    utility_high: float
    worst_case_regret: float
    prediction: EnginePrediction

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine.value,
            "feasible": self.feasible,
            "rejection_reasons": list(self.rejection_reasons),
            "probability_low": self.probability_low,
            "probability_high": self.probability_high,
            "utility_low": self.utility_low,
            "utility_high": self.utility_high,
            "worst_case_regret": self.worst_case_regret,
            "prediction": self.prediction.to_dict(),
        }


@dataclass(frozen=True)
class RobustSelectionResult:
    decision: EngineDecision
    candidates: tuple[RobustCandidate, ...]
    config: RobustSelectionConfig

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "config": asdict(self.config),
        }


class MinimaxRegretSelector:
    def __init__(
        self,
        *,
        config: RobustSelectionConfig | None = None,
        e2b_enabled: bool = False,
    ) -> None:
        self.config = config or RobustSelectionConfig()
        self.e2b_enabled = e2b_enabled

    def select(
        self,
        features: FeatureVector,
        predictions: Mapping[Engine, EnginePrediction],
    ) -> EngineDecision:
        return self.select_with_trace(features, predictions).decision

    def select_with_trace(
        self,
        features: FeatureVector,
        predictions: Mapping[Engine, EnginePrediction],
        *,
        probability_uncertainty: Mapping[Engine, float] | None = None,
    ) -> RobustSelectionResult:
        if Engine.FIREWORKS not in predictions:
            raise ValueError("Fireworks prediction is required for fail-closed selection.")
        uncertainty = probability_uncertainty or {}
        deadline_ms = _deadline_ms(features)
        preliminary = [
            self._candidate(prediction, float(uncertainty.get(engine, 0.0)), deadline_ms=deadline_ms)
            for engine, prediction in sorted(predictions.items(), key=lambda item: item[0].value)
        ]
        feasible = [candidate for candidate in preliminary if candidate.feasible]
        if not feasible:
            fallback = predictions[Engine.FIREWORKS]
            decision = EngineDecision.fireworks_safe_fallback("no_engine_passed_robust_accuracy_and_resource_gates")
            candidates = tuple(_with_regret(candidate, 0.0) for candidate in preliminary)
            return RobustSelectionResult(decision=decision, candidates=candidates, config=self.config)

        regrets = {
            candidate.engine: max(
                0.0,
                max(other.utility_high - candidate.utility_low for other in feasible),
            )
            for candidate in feasible
        }
        completed = tuple(
            _with_regret(candidate, regrets.get(candidate.engine, 0.0))
            for candidate in preliminary
        )
        selected = min(
            (candidate for candidate in completed if candidate.feasible),
            key=lambda candidate: (
                candidate.worst_case_regret,
                -candidate.probability_low,
                candidate.prediction.expected_fireworks_tokens,
                candidate.prediction.expected_latency_ms,
                candidate.engine.value,
            ),
        )
        feasible_engines = tuple(candidate.engine for candidate in completed if candidate.feasible)
        decision = EngineDecision(
            engine=selected.engine,
            reason="minimax_regret_after_robust_accuracy_resource_gates",
            feasible_engines=feasible_engines,
            probability_correct=selected.prediction.probability_correct,
            worst_case_regret=selected.worst_case_regret,
            safe_fallback=False,
        )
        return RobustSelectionResult(decision=decision, candidates=completed, config=self.config)

    def _candidate(self, prediction: EnginePrediction, uncertainty: float, *, deadline_ms: float) -> RobustCandidate:
        if not 0 <= uncertainty <= 1:
            raise ValueError("Probability uncertainty must be in [0, 1].")
        probability_low = max(0.0, prediction.probability_correct - uncertainty)
        probability_high = min(1.0, prediction.probability_correct + uncertainty)
        failure_low = max(0.0, prediction.probability_runtime_failure - 0.02)
        failure_high = min(1.0, prediction.probability_runtime_failure + 0.02)
        ratio = self.config.resource_uncertainty_ratio
        latency_low = prediction.expected_latency_ms * (1.0 - ratio)
        latency_high = prediction.expected_latency_ms * (1.0 + ratio)
        tokens_low = prediction.expected_fireworks_tokens * (1.0 - ratio)
        tokens_high = prediction.expected_fireworks_tokens * (1.0 + ratio)
        reasons: list[str] = []
        if prediction.engine is Engine.GEMMA_E2B and not self.e2b_enabled:
            reasons.append("e2b_policy_disabled")
        if probability_low < self.config.accuracy_gate:
            reasons.append("accuracy_lower_bound_below_gate")
        if failure_high > self.config.max_runtime_failure:
            reasons.append("runtime_failure_upper_bound_above_gate")
        if prediction.expected_peak_memory_mb > self.config.max_peak_memory_mb:
            reasons.append("peak_memory_above_gate")
        if latency_high + self.config.deadline_reserve_ms > deadline_ms:
            reasons.append("deadline_reserve_exhausted")
        utility_low = (
            self.config.accuracy_reward * probability_low
            - self.config.remote_token_penalty * tokens_high
            - self.config.latency_penalty * latency_high
            - self.config.failure_penalty * failure_high
        )
        utility_high = (
            self.config.accuracy_reward * probability_high
            - self.config.remote_token_penalty * tokens_low
            - self.config.latency_penalty * latency_low
            - self.config.failure_penalty * failure_low
        )
        return RobustCandidate(
            engine=prediction.engine,
            feasible=not reasons,
            rejection_reasons=tuple(reasons),
            probability_low=probability_low,
            probability_high=probability_high,
            utility_low=utility_low,
            utility_high=utility_high,
            worst_case_regret=0.0,
            prediction=prediction,
        )


def deterministic_solver_prediction(*, accepted: bool, model_version: str = "solver-manifest-v1") -> EnginePrediction:
    return EnginePrediction(
        engine=Engine.DETERMINISTIC,
        probability_correct=1.0 if accepted else 0.0,
        expected_latency_ms=1.0 if accepted else 0.0,
        expected_fireworks_tokens=0.0,
        probability_runtime_failure=0.0 if accepted else 1.0,
        expected_peak_memory_mb=1.0 if accepted else 0.0,
        model_version=model_version,
    )


def _with_regret(candidate: RobustCandidate, regret: float) -> RobustCandidate:
    return RobustCandidate(
        engine=candidate.engine,
        feasible=candidate.feasible,
        rejection_reasons=candidate.rejection_reasons,
        probability_low=candidate.probability_low,
        probability_high=candidate.probability_high,
        utility_low=candidate.utility_low,
        utility_high=candidate.utility_high,
        worst_case_regret=regret,
        prediction=candidate.prediction,
    )


def _deadline_ms(features: FeatureVector) -> float:
    values = dict(zip(features.names, features.values, strict=True))
    ratio = values.get("struct.deadline_remaining_ratio", 1.0)
    return max(0.0, min(1.0, ratio)) * 10 * 60 * 1000.0
