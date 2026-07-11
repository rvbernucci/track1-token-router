from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from router.core.contracts import TaskAssessment


@dataclass(frozen=True)
class E2BMatrixDecision:
    probe: bool
    probability: float
    threshold: float
    reason: str


@dataclass(frozen=True)
class E2BMatrixGate:
    enabled: bool
    threshold: float
    score_names: tuple[str, ...]
    models: Mapping[str, tuple[float, ...]]
    artifact_sha256: str

    @classmethod
    def load(cls, path: Path, *, expected_sha256: str | None = None) -> "E2BMatrixGate":
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if expected_sha256 and digest != expected_sha256:
            raise ValueError("E2B matrix policy SHA-256 mismatch.")
        payload = json.loads(raw)
        if payload.get("schema_version") != "e2b-270m-matrix-regression-v1":
            raise ValueError("E2B matrix policy schema is invalid.")
        score_names = tuple(payload.get("score_feature_names", ()))
        raw_models = payload.get("models_by_intent")
        if len(score_names) != 5 or not isinstance(raw_models, Mapping):
            raise ValueError("E2B per-intent matrix is missing.")
        models: dict[str, tuple[float, ...]] = {}
        for intent, coefficients in raw_models.items():
            if not isinstance(coefficients, list) or len(coefficients) != len(score_names) + 1:
                raise ValueError("E2B per-intent coefficients are invalid.")
            values = tuple(float(value) for value in coefficients)
            if any(not math.isfinite(value) for value in values):
                raise ValueError("E2B per-intent coefficients must be finite.")
            models[str(intent)] = values
        threshold = float(payload["decision_threshold"])
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("E2B matrix threshold is invalid.")
        return cls(payload.get("default_enabled") is True, threshold, score_names, models, digest)

    def decide(self, assessment: TaskAssessment) -> E2BMatrixDecision:
        coefficients = self.models.get(assessment.intent.value)
        if not self.enabled or coefficients is None:
            return E2BMatrixDecision(False, 0.0, self.threshold, "matrix_disabled_or_unknown_intent")
        scores = assessment.scores.to_dict()
        values = [float(scores[name]) / 10.0 for name in self.score_names]
        logit = coefficients[0] + sum(weight * value for weight, value in zip(coefficients[1:], values, strict=True))
        probability = 1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, logit))))
        return E2BMatrixDecision(
            probability >= self.threshold,
            probability,
            self.threshold,
            "probe_e2b" if probability >= self.threshold else "matrix_below_threshold",
        )
