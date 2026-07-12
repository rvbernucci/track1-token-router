from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from router.core.contracts import TaskAssessment
from router.orchestration.e2b_mechanical_features import extract_e2b_mechanical_features


@dataclass(frozen=True)
class E2BMatrixDecision:
    probe: bool
    probability: float
    threshold: float
    reason: str
    feature_schema_version: str | None = None


@dataclass(frozen=True)
class E2BMatrixGate:
    enabled: bool
    threshold: float
    score_names: tuple[str, ...]
    models: Mapping[str, tuple[float, ...]]
    allowed_intents: frozenset[str]
    artifact_sha256: str
    thresholds_by_intent: Mapping[str, float]
    mechanical_feature_names: tuple[str, ...] = ()
    calibrators_by_intent: Mapping[str, tuple[float, float]] | None = None
    normalization_by_intent: Mapping[str, tuple[tuple[float, ...], tuple[float, ...]]] | None = None

    @classmethod
    def load(cls, path: Path, *, expected_sha256: str | None = None) -> "E2BMatrixGate":
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if expected_sha256 and digest != expected_sha256:
            raise ValueError("E2B matrix policy SHA-256 mismatch.")
        payload = json.loads(raw)
        schema_version = payload.get("schema_version")
        if schema_version not in {"e2b-270m-matrix-regression-v1", "e2b-category-matrix-regression-v2"}:
            raise ValueError("E2B matrix policy schema is invalid.")
        score_names = tuple(payload.get("score_feature_names", ()))
        raw_models = payload.get("models_by_intent")
        if len(score_names) != 5 or not isinstance(raw_models, Mapping):
            raise ValueError("E2B per-intent matrix is missing.")
        models: dict[str, tuple[float, ...]] = {}
        mechanical_names = tuple(payload.get("mechanical_feature_names", ()))
        if schema_version.endswith("v2") and (
            not mechanical_names or not all(isinstance(name, str) and name for name in mechanical_names)
        ):
            raise ValueError("E2B v2 mechanical feature contract is invalid.")
        dimensions = len(score_names) + len(mechanical_names)
        for intent, coefficients in raw_models.items():
            if not isinstance(coefficients, list) or len(coefficients) != dimensions + 1:
                raise ValueError("E2B per-intent coefficients are invalid.")
            values = tuple(float(value) for value in coefficients)
            if any(not math.isfinite(value) for value in values):
                raise ValueError("E2B per-intent coefficients must be finite.")
            models[str(intent)] = values
        threshold = float(payload["decision_threshold"])
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("E2B matrix threshold is invalid.")
        configured_intents = payload.get("allowed_intents", list(models))
        if not isinstance(configured_intents, list) or not all(isinstance(value, str) for value in configured_intents):
            raise ValueError("E2B allowed intents are invalid.")
        allowed_intents = frozenset(configured_intents)
        if not allowed_intents.issubset(models):
            raise ValueError("E2B allowed intents contain an unknown intent.")
        raw_thresholds = payload.get("thresholds_by_intent", {})
        if schema_version.endswith("v2") and (
            not isinstance(raw_thresholds, Mapping) or set(raw_thresholds) != set(models)
        ):
            raise ValueError("E2B v2 thresholds_by_intent are invalid.")
        thresholds = {
            intent: float(raw_thresholds.get(intent, threshold))
            for intent in models
        }
        if any(not 0.0 <= value <= 1.0 for value in thresholds.values()):
            raise ValueError("E2B per-intent threshold is invalid.")
        raw_calibrators = payload.get("calibrators_by_intent", {})
        calibrators: dict[str, tuple[float, float]] = {}
        normalizations: dict[str, tuple[tuple[float, ...], tuple[float, ...]]] = {}
        if schema_version.endswith("v2"):
            if not isinstance(raw_calibrators, Mapping) or set(raw_calibrators) != set(models):
                raise ValueError("E2B v2 calibrators_by_intent are invalid.")
            for intent, coefficients in raw_calibrators.items():
                if not isinstance(coefficients, list) or len(coefficients) != 2:
                    raise ValueError("E2B v2 calibrator coefficients are invalid.")
                values = tuple(float(value) for value in coefficients)
                if any(not math.isfinite(value) for value in values):
                    raise ValueError("E2B v2 calibrator coefficients must be finite.")
                calibrators[str(intent)] = (values[0], values[1])
            raw_normalizations = payload.get("normalization_by_intent")
            if not isinstance(raw_normalizations, Mapping) or set(raw_normalizations) != set(models):
                raise ValueError("E2B v2 normalization_by_intent is invalid.")
            for intent, normalization in raw_normalizations.items():
                if not isinstance(normalization, Mapping):
                    raise ValueError("E2B v2 normalization payload is invalid.")
                means = normalization.get("mean")
                scales = normalization.get("scale")
                if not isinstance(means, list) or not isinstance(scales, list) or len(means) != dimensions or len(scales) != dimensions:
                    raise ValueError("E2B v2 normalization dimensions are invalid.")
                mean_values = tuple(float(value) for value in means)
                scale_values = tuple(float(value) for value in scales)
                if any(not math.isfinite(value) for value in (*mean_values, *scale_values)) or any(value <= 0 for value in scale_values):
                    raise ValueError("E2B v2 normalization values are invalid.")
                normalizations[str(intent)] = (mean_values, scale_values)
        return cls(
            payload.get("default_enabled") is True,
            threshold,
            score_names,
            models,
            allowed_intents,
            digest,
            thresholds,
            mechanical_names,
            calibrators,
            normalizations,
        )

    def decide(self, assessment: TaskAssessment, prompt: str | None = None) -> E2BMatrixDecision:
        coefficients = self.models.get(assessment.intent.value)
        threshold = self.thresholds_by_intent.get(assessment.intent.value, self.threshold)
        if not self.enabled or coefficients is None or assessment.intent.value not in self.allowed_intents:
            return E2BMatrixDecision(False, 0.0, threshold, "matrix_disabled_or_unknown_intent")
        scores = assessment.scores.to_dict()
        values = [float(scores[name]) / 10.0 for name in self.score_names]
        feature_schema_version = None
        if self.mechanical_feature_names:
            if not prompt:
                return E2BMatrixDecision(False, 0.0, threshold, "matrix_missing_mechanical_features")
            extracted = extract_e2b_mechanical_features(prompt)
            observed = extracted.to_dict()["features"]
            feature_schema_version = extracted.schema_version
            if any(name not in observed for name in self.mechanical_feature_names):
                return E2BMatrixDecision(False, 0.0, threshold, "matrix_feature_schema_mismatch")
            values.extend(float(observed[name]) for name in self.mechanical_feature_names)
        normalization = (self.normalization_by_intent or {}).get(assessment.intent.value)
        if normalization is not None:
            means, scales = normalization
            values = [
                (value - mean) / scale
                for value, mean, scale in zip(values, means, scales, strict=True)
            ]
        logit = coefficients[0] + sum(weight * value for weight, value in zip(coefficients[1:], values, strict=True))
        probability = 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, logit))))
        calibrator = (self.calibrators_by_intent or {}).get(assessment.intent.value)
        if calibrator is not None:
            bounded = min(1 - 1e-6, max(1e-6, probability))
            raw_logit = math.log(bounded / (1 - bounded))
            calibrated_logit = calibrator[0] + calibrator[1] * raw_logit
            probability = 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, calibrated_logit))))
        return E2BMatrixDecision(
            probability >= threshold,
            probability,
            threshold,
            "probe_e2b" if probability >= threshold else "matrix_below_threshold",
            feature_schema_version,
        )
