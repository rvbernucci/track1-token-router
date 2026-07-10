from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping

from router.core.contracts import AssessmentScores, TaskAssessment


CALIBRATION_SCHEMA_VERSION = "functiongemma-score-calibration-v1"
SCORE_FIELDS = (
    "deterministic_fit",
    "reasoning_demand",
    "knowledge_uncertainty",
    "generation_demand",
    "format_complexity",
)


@dataclass(frozen=True)
class OrdinalCalibration:
    mapping: tuple[float, ...]
    promoted: bool
    raw_mae: float
    calibrated_mae: float

    def __post_init__(self) -> None:
        if len(self.mapping) != 11:
            raise ValueError("OrdinalCalibration requires one value for every score in [0, 10].")
        if any(not 0 <= value <= 10 for value in self.mapping):
            raise ValueError("Calibration values must remain in [0, 10].")
        if any(left > right for left, right in zip(self.mapping, self.mapping[1:])):
            raise ValueError("Calibration mapping must be monotonic.")

    def apply(self, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10:
            raise ValueError("Calibration input must be an integer in [0, 10].")
        selected = self.mapping[value] if self.promoted else float(value)
        return max(0, min(10, int(selected + 0.5)))

    def to_dict(self) -> dict[str, object]:
        return {
            "mapping": list(self.mapping),
            "promoted": self.promoted,
            "raw_mae": self.raw_mae,
            "calibrated_mae": self.calibrated_mae,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "OrdinalCalibration":
        expected = {"mapping", "promoted", "raw_mae", "calibrated_mae"}
        if set(payload) != expected:
            raise ValueError("Ordinal calibration fields do not match the schema.")
        mapping = payload["mapping"]
        if not isinstance(mapping, list) or any(
            isinstance(value, bool) or not isinstance(value, (int, float)) for value in mapping
        ):
            raise ValueError("Ordinal calibration mapping must be a numeric array.")
        promoted = payload["promoted"]
        raw_mae = payload["raw_mae"]
        calibrated_mae = payload["calibrated_mae"]
        if not isinstance(promoted, bool):
            raise ValueError("Ordinal calibration promoted flag must be boolean.")
        for name, value in (("raw_mae", raw_mae), ("calibrated_mae", calibrated_mae)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 10:
                raise ValueError(f"Ordinal calibration {name} must be in [0, 10].")
        if promoted and not float(calibrated_mae) < float(raw_mae):
            raise ValueError("A promoted calibration must improve validation MAE.")
        return cls(
            mapping=tuple(float(value) for value in mapping),
            promoted=promoted,
            raw_mae=float(raw_mae),
            calibrated_mae=float(calibrated_mae),
        )


@dataclass(frozen=True)
class ScoreCalibrationBundle:
    dimensions: Mapping[str, OrdinalCalibration]
    source_sha256: str
    artifact_sha256: str
    schema_version: str = CALIBRATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CALIBRATION_SCHEMA_VERSION:
            raise ValueError(f"Unsupported calibration schema: {self.schema_version!r}.")
        if set(self.dimensions) != set(SCORE_FIELDS):
            raise ValueError("Calibration dimensions do not match the assessment contract.")
        for name, value in (("source_sha256", self.source_sha256), ("artifact_sha256", self.artifact_sha256)):
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise ValueError(f"Calibration {name} must be a lowercase SHA-256 digest.")

    def apply(self, assessment: TaskAssessment) -> TaskAssessment:
        raw = assessment.scores.to_dict()
        calibrated = {name: self.dimensions[name].apply(raw[name]) for name in SCORE_FIELDS}
        return TaskAssessment(
            intent=assessment.intent,
            sub_intent=assessment.sub_intent,
            scores=AssessmentScores(**calibrated),
        )


def load_calibration(path: Path, *, expected_sha256: str | None = None) -> ScoreCalibrationBundle:
    raw = path.read_bytes()
    artifact_sha256 = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and artifact_sha256 != expected_sha256:
        raise ValueError("Calibration artifact SHA-256 does not match the pinned digest.")
    payload = json.loads(raw)
    if not isinstance(payload, Mapping):
        raise ValueError("Calibration artifact must be a JSON object.")
    expected = {"schema_version", "source_sha256", "dimensions"}
    if set(payload) != expected:
        raise ValueError("Calibration artifact fields do not match the schema.")
    dimensions = payload["dimensions"]
    if not isinstance(dimensions, Mapping):
        raise ValueError("Calibration dimensions must be an object.")
    parsed = {
        str(name): OrdinalCalibration.from_mapping(value)
        for name, value in dimensions.items()
        if isinstance(value, Mapping)
    }
    if len(parsed) != len(dimensions):
        raise ValueError("Every calibration dimension must be an object.")
    return ScoreCalibrationBundle(
        schema_version=str(payload["schema_version"]),
        source_sha256=str(payload["source_sha256"]),
        artifact_sha256=artifact_sha256,
        dimensions=parsed,
    )


def fit_ordinal_calibration(pairs: Iterable[tuple[int, int]]) -> OrdinalCalibration:
    values = list(pairs)
    if not values:
        raise ValueError("Calibration requires at least one prediction/gold pair.")
    for predicted, gold in values:
        if not 0 <= predicted <= 10 or not 0 <= gold <= 10:
            raise ValueError("Calibration pairs must be in [0, 10].")
    sums = [0.0] * 11
    weights = [0] * 11
    for predicted, gold in values:
        sums[predicted] += gold
        weights[predicted] += 1
    observed = [(index, sums[index] / weights[index], weights[index]) for index in range(11) if weights[index]]
    blocks: list[list[float]] = []
    for index, value, weight in observed:
        blocks.append([float(index), float(index), value, float(weight)])
        while len(blocks) >= 2 and blocks[-2][2] > blocks[-1][2]:
            right = blocks.pop()
            left = blocks.pop()
            total_weight = left[3] + right[3]
            blocks.append(
                [left[0], right[1], (left[2] * left[3] + right[2] * right[3]) / total_weight, total_weight]
            )
    anchors: dict[int, float] = {}
    for block in blocks:
        for index in range(int(block[0]), int(block[1]) + 1):
            if weights[index]:
                anchors[index] = block[2]
    mapping = tuple(_interpolate(index, anchors) for index in range(11))
    raw_mae = mean(abs(predicted - gold) for predicted, gold in values)
    calibrated_mae = mean(abs(max(0, min(10, int(mapping[predicted] + 0.5))) - gold) for predicted, gold in values)
    return OrdinalCalibration(
        mapping=mapping,
        promoted=calibrated_mae + 1e-12 < raw_mae,
        raw_mae=raw_mae,
        calibrated_mae=calibrated_mae,
    )


def _interpolate(index: int, anchors: dict[int, float]) -> float:
    if not anchors:
        return float(index)
    if index in anchors:
        return max(0.0, min(10.0, anchors[index]))
    lower = max((value for value in anchors if value < index), default=None)
    upper = min((value for value in anchors if value > index), default=None)
    if lower is None:
        return max(0.0, min(10.0, anchors[upper]))  # type: ignore[index]
    if upper is None:
        return max(0.0, min(10.0, anchors[lower]))
    fraction = (index - lower) / (upper - lower)
    return max(0.0, min(10.0, anchors[lower] + fraction * (anchors[upper] - anchors[lower])))
