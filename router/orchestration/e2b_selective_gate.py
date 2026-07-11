from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from router.core.contracts import FeatureVector, TaskEnvelope
from router.orchestration.final_validator import AnswerContractKind, apply_answer_contract


SCHEMA_VERSION = "e2b-selective-policy-v1"
RESPONSE_FEATURE_NAMES = (
    "response.validator_valid",
    "response.constraint_present",
    "response.constraint_satisfied",
    "response.refusal",
    "response.likely_token_cap",
    "response.canonical_sentiment",
    "response.lexical_overlap",
    "response.answer_words_log",
    "response.answer_to_prompt_ratio",
    "response.sentences_log",
    "response.terminal_marker",
    "response.fence_balanced",
)
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it",
    "of", "on", "or", "that", "the", "this", "to", "was", "were", "with",
}
_REFUSAL = re.compile(
    r"\b(?:i can(?:not|'t)|unable to|insufficient information|not enough information|cannot determine)\b",
    re.IGNORECASE,
)
_SENTIMENT_TASK = re.compile(r"\b(?:sentiment|positive|negative|neutral)\b", re.IGNORECASE)
_CANONICAL_SENTIMENT = {"positive", "negative", "neutral", "mixed"}


@dataclass(frozen=True)
class E2BResponseSignals:
    features: FeatureVector
    validated_answer: str
    validator_reason: str
    hard_rejections: tuple[str, ...]

    @property
    def mechanically_valid(self) -> bool:
        return not self.hard_rejections

    def to_dict(self) -> dict[str, Any]:
        return {
            "features": self.features.to_dict(),
            "validated_answer": self.validated_answer,
            "validator_reason": self.validator_reason,
            "hard_rejections": list(self.hard_rejections),
            "mechanically_valid": self.mechanically_valid,
        }


@dataclass(frozen=True)
class E2BSelectiveDecision:
    probe: bool
    accepted: bool
    pre_probability: float
    post_probability: float | None
    reason: str
    answer: str = ""
    response_signals: E2BResponseSignals | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["response_signals"] = self.response_signals.to_dict() if self.response_signals else None
        return payload


@dataclass(frozen=True)
class _LogisticModel:
    feature_names: tuple[str, ...]
    coefficients: tuple[float, ...]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any], *, name: str) -> "_LogisticModel":
        names = payload.get("feature_names")
        coefficients = payload.get("coefficients")
        if (
            not isinstance(names, list)
            or not names
            or any(not isinstance(item, str) or not item for item in names)
            or len(set(names)) != len(names)
        ):
            raise ValueError(f"{name}.feature_names must be unique non-empty strings.")
        if (
            not isinstance(coefficients, list)
            or len(coefficients) != len(names)
            or any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in coefficients)
        ):
            raise ValueError(f"{name}.coefficients must be finite and aligned with feature_names.")
        return cls(tuple(names), tuple(float(item) for item in coefficients))

    def predict(self, features: Mapping[str, float]) -> float:
        values = [_feature_value(name, features) for name in self.feature_names]
        return _sigmoid(sum(left * right for left, right in zip(self.coefficients, values, strict=True)))


@dataclass(frozen=True)
class E2BSelectivePolicy:
    enabled: bool
    pre_threshold: float
    post_threshold: float
    pre_model: _LogisticModel
    post_model: _LogisticModel
    artifact_sha256: str
    reason: str

    @classmethod
    def load(cls, path: Path, *, expected_sha256: str | None = None) -> "E2BSelectivePolicy":
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValueError("E2B selective policy SHA-256 does not match the pinned digest.")
        payload = json.loads(raw)
        if not isinstance(payload, Mapping) or payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("E2B selective policy schema is invalid.")
        enabled = payload.get("default_enabled")
        thresholds = payload.get("thresholds")
        models = payload.get("models")
        if not isinstance(enabled, bool) or not isinstance(thresholds, Mapping) or not isinstance(models, Mapping):
            raise ValueError("E2B selective policy is missing enabled, thresholds or models.")
        pre_threshold = _probability(thresholds.get("pre_probe"), "thresholds.pre_probe")
        post_threshold = _probability(thresholds.get("post_accept"), "thresholds.post_accept")
        reason = payload.get("reason")
        if not isinstance(reason, str) or not reason:
            raise ValueError("E2B selective policy reason is required.")
        pre = models.get("pre_response")
        post = models.get("post_response")
        if not isinstance(pre, Mapping) or not isinstance(post, Mapping):
            raise ValueError("E2B selective policy requires pre_response and post_response models.")
        return cls(
            enabled=enabled,
            pre_threshold=pre_threshold,
            post_threshold=post_threshold,
            pre_model=_LogisticModel.from_mapping(pre, name="models.pre_response"),
            post_model=_LogisticModel.from_mapping(post, name="models.post_response"),
            artifact_sha256=digest,
            reason=reason,
        )

    def pre_probability(self, task_features: FeatureVector) -> float:
        return self.pre_model.predict(_feature_mapping(task_features))

    def should_probe(self, task_features: FeatureVector) -> E2BSelectiveDecision:
        probability = self.pre_probability(task_features)
        if not self.enabled:
            return E2BSelectiveDecision(False, False, probability, None, "selective_policy_disabled")
        if probability < self.pre_threshold:
            return E2BSelectiveDecision(False, False, probability, None, "pre_probability_below_probe_threshold")
        return E2BSelectiveDecision(True, False, probability, None, "probe_e2b_candidate")

    def evaluate(self, task: TaskEnvelope, answer: str, task_features: FeatureVector) -> E2BSelectiveDecision:
        pre = self.pre_probability(task_features)
        signals = extract_e2b_response_signals(task, answer)
        combined = {**_feature_mapping(task_features), **_feature_mapping(signals.features)}
        probability = self.post_model.predict(combined)
        if not self.enabled:
            return E2BSelectiveDecision(False, False, pre, probability, "selective_policy_disabled", response_signals=signals)
        if pre < self.pre_threshold:
            return E2BSelectiveDecision(False, False, pre, probability, "pre_probability_below_probe_threshold", response_signals=signals)
        if not signals.mechanically_valid:
            return E2BSelectiveDecision(
                True,
                False,
                pre,
                probability,
                "mechanical_rejection:" + ",".join(signals.hard_rejections),
                response_signals=signals,
            )
        if probability < self.post_threshold:
            return E2BSelectiveDecision(True, False, pre, probability, "post_probability_below_accept_threshold", response_signals=signals)
        return E2BSelectiveDecision(
            True,
            True,
            pre,
            probability,
            "selective_local_accept",
            answer=signals.validated_answer,
            response_signals=signals,
        )


def extract_e2b_response_signals(task: TaskEnvelope, answer: str) -> E2BResponseSignals:
    validation = apply_answer_contract(task, answer)
    raw_candidate = answer.strip()
    sentiment_task = validation.contract.kind is AnswerContractKind.LABEL and bool(_SENTIMENT_TASK.search(task.input_text))
    raw_canonical_sentiment = raw_candidate.casefold() in _CANONICAL_SENTIMENT
    if sentiment_task and raw_canonical_sentiment:
        candidate = raw_candidate
        validator_valid = True
        validator_reason = "valid_canonical_sentiment"
    else:
        candidate = validation.answer or raw_candidate
        validator_valid = validation.valid
        validator_reason = validation.reason
    prompt_words = _words(task.input_text)
    answer_words = _words(candidate)
    prompt_vocabulary = set(prompt_words)
    content_words = [word for word in answer_words if word not in _STOPWORDS and len(word) > 2]
    overlap = sum(word in prompt_vocabulary for word in content_words) / max(1, len(content_words))
    sentence_count = max(
        len(re.findall(r"[.!?](?:\s|$)", candidate.strip())),
        1 if candidate.strip() else 0,
    )
    constraints = _constraint_checks(task.input_text, candidate, answer_words, sentence_count)
    canonical_sentiment = not sentiment_task or candidate.strip().casefold() in _CANONICAL_SENTIMENT
    refusal = bool(_REFUSAL.search(candidate))
    terminal = bool(candidate.strip()) and candidate.strip()[-1] in ".!?}`])"
    likely_cap = len(answer_words) >= 80 or (len(candidate) >= 500 and not terminal)
    values = (
        float(validator_valid),
        float(bool(constraints)),
        float(all(constraints) if constraints else True),
        float(refusal),
        float(likely_cap),
        float(canonical_sentiment),
        overlap,
        min(1.0, math.log1p(len(answer_words)) / math.log1p(200)),
        min(1.0, math.log1p(len(answer_words)) / max(1.0, math.log1p(len(prompt_words)))),
        min(1.0, math.log1p(sentence_count) / math.log1p(10)),
        float(terminal),
        float(candidate.count("```") % 2 == 0),
    )
    hard_rejections: list[str] = []
    if not validator_valid:
        hard_rejections.append(f"validator:{validator_reason}")
    if constraints and not all(constraints):
        hard_rejections.append("explicit_constraint_mismatch")
    if refusal:
        hard_rejections.append("model_refusal")
    if sentiment_task and not canonical_sentiment:
        hard_rejections.append("noncanonical_sentiment")
    return E2BResponseSignals(
        features=FeatureVector(names=RESPONSE_FEATURE_NAMES, values=values),
        validated_answer=candidate,
        validator_reason=validator_reason,
        hard_rejections=tuple(hard_rejections),
    )


def combine_feature_vectors(left: FeatureVector, right: FeatureVector) -> FeatureVector:
    return FeatureVector(names=(*left.names, *right.names), values=(*left.values, *right.values))


def _constraint_checks(prompt: str, answer: str, answer_words: list[str], sentence_count: int) -> list[bool]:
    checks: list[bool] = []
    patterns = (
        (r"exactly\s+(\d+)\s+sentences?", sentence_count),
        (r"exactly\s+(\d+)\s+words?", len(answer_words)),
        (r"exactly\s+(\d+)\s+(?:bullet(?: points?)?|items?)", len(re.findall(r"(?m)^\s*(?:[-*]|\d+[.)])\s+", answer))),
    )
    for pattern, actual in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            checks.append(actual == int(match.group(1)))
    return checks


def _feature_mapping(features: FeatureVector) -> dict[str, float]:
    return dict(zip(features.names, features.values, strict=True))


def _feature_value(name: str, values: Mapping[str, float]) -> float:
    if name in values:
        return float(values[name])
    score = lambda key: float(values.get(f"score.{key}", 0.0))
    derived = {
        "bias": 1.0,
        "square.score.deterministic_fit": score("deterministic_fit") ** 2,
        "square.score.reasoning_demand": score("reasoning_demand") ** 2,
        "square.score.knowledge_uncertainty": score("knowledge_uncertainty") ** 2,
        "square.score.generation_demand": score("generation_demand") ** 2,
        "square.score.format_complexity": score("format_complexity") ** 2,
        "interaction.reasoning_x_format": score("reasoning_demand") * score("format_complexity"),
        "interaction.generation_x_format": score("generation_demand") * score("format_complexity"),
        "interaction.input_length_x_generation": float(values.get("struct.input_tokens_log", 0.0)) * score("generation_demand"),
    }
    if name not in derived:
        raise ValueError(f"Selective E2B model cannot supply feature {name!r}.")
    return derived[name]


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-min(60.0, value)))
    exp_value = math.exp(max(-60.0, value))
    return exp_value / (1.0 + exp_value)


def _probability(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be a probability in [0, 1].")
    return float(value)


def _words(value: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÿ0-9_'-]+", value.casefold())
