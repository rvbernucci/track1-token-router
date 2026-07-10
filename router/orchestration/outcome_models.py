from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from router.core.contracts import Engine, EnginePrediction, FeatureVector


SCHEMA_VERSION = "engine-outcome-models-v1"


@dataclass(frozen=True)
class OutcomeModelBundle:
    models: Mapping[str, Mapping[str, Any]]
    artifact_sha256: str
    matrix_sha256: str
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def load(cls, path: Path, *, expected_sha256: str | None = None) -> "OutcomeModelBundle":
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValueError("Outcome model artifact SHA-256 does not match the pinned digest.")
        payload = json.loads(raw)
        if not isinstance(payload, Mapping) or payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Outcome model artifact has an unsupported schema.")
        models = payload.get("models")
        matrix_sha256 = payload.get("matrix_sha256")
        if not isinstance(models, Mapping) or not _digest(matrix_sha256):
            raise ValueError("Outcome model artifact is missing models or matrix lineage.")
        return cls(
            models={str(key): value for key, value in models.items() if isinstance(value, Mapping)},
            artifact_sha256=digest,
            matrix_sha256=str(matrix_sha256),
        )

    def uncertainty(self, model_id: str, probability: float | None = None) -> float:
        model = self.models[model_id]
        correctness = model["correctness"]
        selected = str(correctness["selected_model"])
        metrics = correctness["held_out_metrics"][selected]
        observations = max(1.0, float(metrics["observations"]))
        sampling = min(0.25, math.sqrt(max(0.0, float(metrics["brier"])) / observations))
        bins = correctness.get("calibration_bins")
        if probability is None or not isinstance(bins, list) or not bins:
            return sampling
        eligible = [
            row for row in bins
            if isinstance(row, Mapping)
            and isinstance(row.get("prediction_max"), (int, float))
            and probability <= float(row["prediction_max"]) + 1e-12
        ]
        selected = eligible[0] if eligible else bins[-1]
        if not isinstance(selected, Mapping) or not isinstance(selected.get("wilson_lower_95"), (int, float)):
            return sampling
        calibration_gap = max(0.0, probability - float(selected["wilson_lower_95"]))
        return min(1.0, max(sampling, calibration_gap))


class OutcomeModelPredictor:
    def __init__(
        self,
        bundle: OutcomeModelBundle,
        *,
        allowed_models: Sequence[str],
        e2b_model_id: str = "gemma4-e2b",
        e2b_combined_memory_mb: float | None = None,
    ) -> None:
        self.bundle = bundle
        self.allowed_models = tuple(allowed_models)
        self.e2b_model_id = e2b_model_id
        self.e2b_combined_memory_mb = e2b_combined_memory_mb

    def predict(self, features: FeatureVector, engine: Engine) -> EnginePrediction:
        if engine is Engine.DETERMINISTIC:
            return EnginePrediction(
                engine=engine,
                probability_correct=0.0,
                expected_latency_ms=0.0,
                expected_fireworks_tokens=0.0,
                probability_runtime_failure=1.0,
                expected_peak_memory_mb=0.0,
                model_version=f"{self.bundle.artifact_sha256}:deterministic_requires_solver",
            )
        if engine is Engine.GEMMA_E2B:
            return self._predict_model(features, self.e2b_model_id, engine)
        candidates = [model for model in self.allowed_models if model in self.bundle.models]
        if not candidates:
            raise ValueError("No observed Fireworks model is both allowed and present in the outcome artifact.")
        predictions = [self._predict_model(features, model, engine) for model in candidates]
        return max(
            predictions,
            key=lambda value: (
                value.probability_correct,
                -value.expected_fireworks_tokens,
                -value.expected_latency_ms,
                value.model_version,
            ),
        )

    def predict_fireworks_model(self, features: FeatureVector, model_id: str) -> EnginePrediction:
        if model_id not in self.allowed_models:
            raise ValueError(f"Fireworks model {model_id!r} is not in ALLOWED_MODELS.")
        return self._predict_model(features, model_id, Engine.FIREWORKS)

    def uncertainty(self, prediction: EnginePrediction) -> float:
        model_id = prediction.model_version.split(":model=", 1)[-1]
        if model_id not in self.bundle.models:
            return 0.0
        return self.bundle.uncertainty(model_id, prediction.probability_correct)

    def _predict_model(self, features: FeatureVector, model_id: str, engine: Engine) -> EnginePrediction:
        if model_id not in self.bundle.models:
            raise ValueError(f"Outcome artifact has no fitted model for {model_id!r}.")
        model = self.bundle.models[model_id]
        probability = _predict_correctness(model["correctness"], features)
        latency = _predict_continuous(model["latency_ms"], features)
        prompt_tokens = _predict_continuous(model["fireworks_prompt_tokens"], features)
        completion_tokens = _predict_continuous(model["fireworks_completion_tokens"], features)
        failure = float(model["runtime_failure"]["probability"])
        memory = model["peak_memory_mb"].get("value")
        memory_mb = float(memory) if isinstance(memory, (int, float)) else 0.0
        if engine is Engine.GEMMA_E2B and self.e2b_combined_memory_mb is not None:
            memory_mb = self.e2b_combined_memory_mb
        remote_tokens = prompt_tokens + completion_tokens if engine is Engine.FIREWORKS else 0.0
        return EnginePrediction(
            engine=engine,
            probability_correct=max(0.0, min(1.0, probability)),
            expected_latency_ms=max(0.0, latency),
            expected_fireworks_tokens=max(0.0, remote_tokens),
            probability_runtime_failure=max(0.0, min(1.0, failure)),
            expected_peak_memory_mb=max(0.0, memory_mb),
            model_version=f"{self.bundle.artifact_sha256}:model={model_id}",
        )


def _predict_correctness(model: Mapping[str, Any], features: FeatureVector) -> float:
    selected = str(model["selected_model"])
    coefficients = _numbers(model["coefficients"])
    if selected == "constant":
        if len(coefficients) != 1:
            raise ValueError("Constant correctness model requires exactly one coefficient.")
        return coefficients[0]
    names = _strings(model["feature_names"])
    values = _runtime_values(features, names)
    if len(values) != len(coefficients):
        raise ValueError("Correctness coefficient and feature dimensions differ.")
    return _sigmoid(sum(left * right for left, right in zip(coefficients, values, strict=True)))


def _predict_continuous(model: Mapping[str, Any], features: FeatureVector) -> float:
    selected = str(model["selected_model"])
    coefficients = _numbers(model["coefficients"])
    if selected == "constant":
        if len(coefficients) != 1:
            raise ValueError("Constant continuous model requires exactly one coefficient.")
        return coefficients[0]
    if selected != "ridge_log1p":
        raise ValueError(f"Unsupported continuous outcome model {selected!r}.")
    values = _runtime_values(features, _strings(model["feature_names"]))
    if len(values) != len(coefficients):
        raise ValueError("Continuous coefficient and feature dimensions differ.")
    return math.expm1(sum(left * right for left, right in zip(coefficients, values, strict=True)))


def _runtime_values(features: FeatureVector, requested_names: Sequence[str]) -> list[float]:
    base = dict(zip(features.names, features.values, strict=True))
    score = lambda name: base.get(f"score.{name}", 0.0)
    derived = {
        "bias": 1.0,
        "square.score.deterministic_fit": score("deterministic_fit") ** 2,
        "square.score.reasoning_demand": score("reasoning_demand") ** 2,
        "square.score.knowledge_uncertainty": score("knowledge_uncertainty") ** 2,
        "square.score.generation_demand": score("generation_demand") ** 2,
        "square.score.format_complexity": score("format_complexity") ** 2,
        "interaction.reasoning_x_format": score("reasoning_demand") * score("format_complexity"),
        "interaction.generation_x_format": score("generation_demand") * score("format_complexity"),
        "interaction.input_length_x_generation": base.get("struct.input_tokens_log", 0.0) * score("generation_demand"),
    }
    values: list[float] = []
    for name in requested_names:
        if name in base:
            values.append(float(base[name]))
        elif name in derived:
            values.append(float(derived[name]))
        else:
            raise ValueError(f"Runtime feature vector cannot supply {name!r}.")
    return values


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-min(value, 60.0)))
    exp_value = math.exp(max(value, -60.0))
    return exp_value / (1.0 + exp_value)


def _numbers(value: Any) -> list[float]:
    if not isinstance(value, list) or any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        raise ValueError("Model coefficients must be a numeric array.")
    return [float(item) for item in value]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError("Model feature names must be a non-empty string array.")
    return list(value)


def _digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)
