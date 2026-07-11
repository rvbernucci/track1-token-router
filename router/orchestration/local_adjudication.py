from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from router.core.contracts import FeatureVector, TaskEnvelope
from router.orchestration.code_verifier import infer_code_task_contract, verify_code_candidate
from router.orchestration.final_validator import apply_answer_contract
from router.orchestration.grounded_verifier import GroundedTaskKind, verify_grounded_candidate
from router.orchestration.proof_engine import ProofType, verify_candidate_against_proof
from router.orchestration.solvers import solve_deterministic


LOCAL_ADJUDICATION_SCHEMA_VERSION = "local-adjudication-policy-v1"
LOCAL_EVIDENCE_SCHEMA_VERSION = "local-adjudication-evidence-v1"
MINIMUM_PROBE_DEADLINE_MS = 100


class VerifierFamily(str, Enum):
    PROOF_MATH = "proof_math"
    PROOF_LOGIC = "proof_logic"
    CODE_SANDBOX = "code_sandbox"
    GROUNDED_NER = "grounded_ner"
    GROUNDED_CONTEXT_QA = "grounded_context_qa"
    GROUNDED_SENTIMENT = "grounded_sentiment"
    GROUNDED_SUMMARY = "grounded_summary"
    NONE = "none"


@dataclass(frozen=True)
class VerifierRegistration:
    family: VerifierFamily
    capability: str
    proof_type: str
    confidence_source: str

    def to_dict(self) -> dict[str, str]:
        payload = asdict(self)
        payload["family"] = self.family.value
        return payload


VERIFIER_REGISTRY: tuple[VerifierRegistration, ...] = (
    VerifierRegistration(VerifierFamily.PROOF_MATH, "bounded math", "proof-envelope-v1", "executable proof"),
    VerifierRegistration(VerifierFamily.PROOF_LOGIC, "bounded logic", "proof-envelope-v1", "unique finite proof"),
    VerifierRegistration(VerifierFamily.CODE_SANDBOX, "supported Python functions", "code-verification-report-v1", "AST and sandbox tests"),
    VerifierRegistration(VerifierFamily.GROUNDED_NER, "typed NER", "source-span-v1", "schema and source spans"),
    VerifierRegistration(VerifierFamily.GROUNDED_CONTEXT_QA, "context QA", "source-span-v1", "unique source support"),
    VerifierRegistration(VerifierFamily.GROUNDED_SENTIMENT, "high-margin sentiment", "source-span-v1", "lexical/local-model agreement"),
    VerifierRegistration(VerifierFamily.GROUNDED_SUMMARY, "extractive summary", "source-span-v1", "extractive source spans"),
)


EVIDENCE_FEATURE_NAMES = (
    "evidence.verifier_supported",
    "evidence.verifier_accepted",
    "evidence.answer_contract_valid",
    "evidence.proof_valid",
    "evidence.proof_unique",
    "evidence.deterministic_e2b_agreement",
    "evidence.normalized_answer_equal",
    "evidence.execution_passed",
    "evidence.grounding_passed",
    "evidence.truncation_detected",
    "evidence.span_count",
    *(f"verifier_family.{family.value}" for family in VerifierFamily if family is not VerifierFamily.NONE),
)


@dataclass(frozen=True)
class LocalAdjudicationEvidence:
    task_id: str
    verifier_family: VerifierFamily
    verifier_supported: bool
    verifier_accepted: bool
    answer_contract_valid: bool
    proof_valid: bool
    proof_unique: bool
    deterministic_e2b_agreement: bool
    normalized_answer_equal: bool
    execution_passed: bool
    grounding_passed: bool
    truncation_detected: bool
    normalized_answer: str
    verifier_reason: str
    prompt_sha256: str
    candidate_sha256: str
    proof_payload: Mapping[str, Any] | None = None
    span_count: int = 0
    schema_version: str = LOCAL_EVIDENCE_SCHEMA_VERSION

    @property
    def hard_gate_passed(self) -> bool:
        return (
            self.verifier_supported
            and self.verifier_accepted
            and self.answer_contract_valid
            and not self.truncation_detected
        )

    def to_feature_vector(self) -> FeatureVector:
        values = (
            float(self.verifier_supported),
            float(self.verifier_accepted),
            float(self.answer_contract_valid),
            float(self.proof_valid),
            float(self.proof_unique),
            float(self.deterministic_e2b_agreement),
            float(self.normalized_answer_equal),
            float(self.execution_passed),
            float(self.grounding_passed),
            float(self.truncation_detected),
            min(1.0, self.span_count / 8.0),
            *(float(self.verifier_family is family) for family in VerifierFamily if family is not VerifierFamily.NONE),
        )
        return FeatureVector(names=EVIDENCE_FEATURE_NAMES, values=values)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["verifier_family"] = self.verifier_family.value
        payload["hard_gate_passed"] = self.hard_gate_passed
        payload["proof_payload"] = dict(self.proof_payload) if self.proof_payload else None
        return payload


@dataclass(frozen=True)
class LocalAdjudicationDecision:
    route: str
    probe: bool
    accepted: bool
    pre_probability: float
    post_probability: float | None
    threshold: float | None
    reason: str
    answer: str = ""
    evidence: LocalAdjudicationEvidence | None = None
    policy_sha256: str = ""
    drift_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence"] = self.evidence.to_dict() if self.evidence else None
        return payload


@dataclass(frozen=True)
class _LogisticModel:
    feature_names: tuple[str, ...]
    coefficients: tuple[float, ...]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any], name: str) -> "_LogisticModel":
        names = payload.get("feature_names")
        coefficients = payload.get("coefficients")
        if not isinstance(names, list) or not names or any(not isinstance(item, str) for item in names):
            raise ValueError(f"{name}.feature_names is invalid.")
        if len(set(names)) != len(names):
            raise ValueError(f"{name}.feature_names must be unique.")
        if (
            not isinstance(coefficients, list)
            or len(coefficients) != len(names)
            or any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in coefficients)
        ):
            raise ValueError(f"{name}.coefficients is invalid.")
        return cls(tuple(names), tuple(float(item) for item in coefficients))

    def predict(self, values: Mapping[str, float]) -> float:
        return _sigmoid(
            sum(coefficient * _feature_value(name, values) for name, coefficient in zip(self.feature_names, self.coefficients, strict=True))
        )


@dataclass(frozen=True)
class LocalAdjudicationPolicy:
    enabled: bool
    pre_threshold: float
    post_thresholds: Mapping[VerifierFamily, float]
    enabled_families: frozenset[VerifierFamily]
    pre_model: _LogisticModel
    post_model: _LogisticModel
    artifact_sha256: str
    reason: str
    maximum_drift_score: float
    drift_threshold_penalty: float
    distribution_reference: Mapping[str, Any]

    @classmethod
    def load(cls, path: Path, *, expected_sha256: str | None = None) -> "LocalAdjudicationPolicy":
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if expected_sha256 and expected_sha256 != digest:
            raise ValueError("Local adjudication policy SHA-256 mismatch.")
        payload = json.loads(raw)
        if not isinstance(payload, Mapping) or payload.get("schema_version") != LOCAL_ADJUDICATION_SCHEMA_VERSION:
            raise ValueError("Local adjudication policy schema is invalid.")
        models = payload.get("models")
        thresholds = payload.get("thresholds")
        cohorts = payload.get("cohorts")
        drift = payload.get("distribution_shift")
        if not all(isinstance(item, Mapping) for item in (models, thresholds, cohorts, drift)):
            raise ValueError("Local adjudication policy sections are missing.")
        enabled_families: set[VerifierFamily] = set()
        post_thresholds: dict[VerifierFamily, float] = {}
        for name, row in cohorts.items():
            if not isinstance(row, Mapping):
                raise ValueError("Invalid cohort policy.")
            family = VerifierFamily(name)
            if row.get("enabled") is True:
                enabled_families.add(family)
            post_thresholds[family] = _probability(row.get("post_threshold"), f"cohorts.{name}.post_threshold")
        reason = payload.get("reason")
        if not isinstance(reason, str) or not reason:
            raise ValueError("Local adjudication policy reason is required.")
        reference = drift.get("reference")
        if not isinstance(reference, Mapping):
            raise ValueError("Distribution-shift reference is required.")
        return cls(
            enabled=payload.get("default_enabled") is True,
            pre_threshold=_probability(thresholds.get("pre_probe"), "thresholds.pre_probe"),
            post_thresholds=post_thresholds,
            enabled_families=frozenset(enabled_families),
            pre_model=_LogisticModel.from_mapping(models["pre_response"], "models.pre_response"),
            post_model=_LogisticModel.from_mapping(models["post_response"], "models.post_response"),
            artifact_sha256=digest,
            reason=reason,
            maximum_drift_score=_probability(drift.get("maximum_score"), "distribution_shift.maximum_score"),
            drift_threshold_penalty=_probability(drift.get("threshold_penalty"), "distribution_shift.threshold_penalty"),
            distribution_reference=dict(reference),
        )

    def pre_probability(self, task_features: FeatureVector) -> float:
        return self.pre_model.predict(_mapping(task_features))

    def batch_drift_score(self, assessments: Sequence[Mapping[str, Any]]) -> float:
        return distribution_shift_score(self.distribution_reference, assessments)

    def should_probe(self, task_features: FeatureVector, *, deadline_remaining_ms: int) -> LocalAdjudicationDecision:
        probability = self.pre_probability(task_features)
        if not self.enabled:
            return self._remote(False, probability, None, None, "local_policy_disabled")
        if deadline_remaining_ms < MINIMUM_PROBE_DEADLINE_MS:
            return self._remote(False, probability, None, None, "insufficient_probe_deadline")
        if probability < self.pre_threshold:
            return self._remote(False, probability, None, self.pre_threshold, "pre_probability_below_threshold")
        return LocalAdjudicationDecision(
            route="e2b_probe",
            probe=True,
            accepted=False,
            pre_probability=probability,
            post_probability=None,
            threshold=self.pre_threshold,
            reason="probe_local_candidate",
            policy_sha256=self.artifact_sha256,
        )

    def adjudicate(
        self,
        task: TaskEnvelope,
        candidate: str,
        task_features: FeatureVector,
        *,
        deadline_remaining_ms: int,
        drift_score: float = 0.0,
    ) -> LocalAdjudicationDecision:
        pre = self.pre_probability(task_features)
        if not self.enabled:
            return self._remote(False, pre, None, None, "local_policy_disabled")
        if deadline_remaining_ms < MINIMUM_PROBE_DEADLINE_MS:
            return self._remote(False, pre, None, None, "insufficient_probe_deadline")
        if pre < self.pre_threshold:
            return self._remote(False, pre, None, self.pre_threshold, "pre_probability_below_threshold")
        try:
            evidence = build_local_adjudication_evidence(task, candidate)
            combined = {**_mapping(task_features), **_mapping(evidence.to_feature_vector())}
            post = self.post_model.predict(combined)
        except Exception as exc:
            return self._remote(True, pre, None, None, f"adjudication_failure:{type(exc).__name__}")
        if evidence.verifier_family not in self.enabled_families:
            return self._remote(True, pre, post, None, "verifier_family_not_enabled", evidence=evidence)
        threshold = self.post_thresholds[evidence.verifier_family]
        drift = max(0.0, min(1.0, float(drift_score)))
        if drift > self.maximum_drift_score:
            return self._remote(True, pre, post, threshold, "distribution_shift_abstention", evidence=evidence, drift=drift)
        threshold = min(0.999, threshold + drift * self.drift_threshold_penalty)
        if not evidence.hard_gate_passed:
            return self._remote(True, pre, post, threshold, f"hard_gate:{evidence.verifier_reason}", evidence=evidence, drift=drift)
        if post < threshold:
            return self._remote(True, pre, post, threshold, "post_probability_below_threshold", evidence=evidence, drift=drift)
        return LocalAdjudicationDecision(
            route="local",
            probe=True,
            accepted=True,
            pre_probability=pre,
            post_probability=post,
            threshold=threshold,
            reason="verified_local_release",
            answer=evidence.normalized_answer,
            evidence=evidence,
            policy_sha256=self.artifact_sha256,
            drift_score=drift,
        )

    def _remote(
        self,
        probe: bool,
        pre: float,
        post: float | None,
        threshold: float | None,
        reason: str,
        *,
        evidence: LocalAdjudicationEvidence | None = None,
        drift: float = 0.0,
    ) -> LocalAdjudicationDecision:
        return LocalAdjudicationDecision(
            route="fireworks",
            probe=probe,
            accepted=False,
            pre_probability=pre,
            post_probability=post,
            threshold=threshold,
            reason=reason,
            evidence=evidence,
            policy_sha256=self.artifact_sha256,
            drift_score=drift,
        )

    @staticmethod
    def authorize_remote_model(model: str, allowed_models: Sequence[str]) -> str:
        allowed = tuple(item.strip() for item in allowed_models if item.strip())
        if not allowed or model not in allowed:
            raise ValueError("Remote model is not present in runtime ALLOWED_MODELS.")
        return model


def build_local_adjudication_evidence(task: TaskEnvelope, candidate: str) -> LocalAdjudicationEvidence:
    prompt_hash = hashlib.sha256(task.input_text.encode()).hexdigest()
    candidate_hash = hashlib.sha256(candidate.encode()).hexdigest()
    truncation = _looks_truncated(candidate)
    code_contract = infer_code_task_contract(task)
    if code_contract is not None:
        report = verify_code_candidate(task, candidate)
        deterministic = solve_deterministic(task)
        normalized = report.normalized_code or candidate.strip()
        agreement = bool(deterministic and _normalized(deterministic.answer) == _normalized(normalized))
        contract_valid = not any(reason.startswith("answer_contract:") for reason in report.rejection_reasons)
        return LocalAdjudicationEvidence(
            task_id=task.id or prompt_hash[:16],
            verifier_family=VerifierFamily.CODE_SANDBOX,
            verifier_supported=True,
            verifier_accepted=report.accepted,
            answer_contract_valid=contract_valid,
            proof_valid=report.dynamic_passed,
            proof_unique=report.dynamic_passed,
            deterministic_e2b_agreement=agreement,
            normalized_answer_equal=report.accepted,
            execution_passed=report.dynamic_passed,
            grounding_passed=False,
            truncation_detected=truncation,
            normalized_answer=normalized,
            verifier_reason=report.rejection_reasons[0] if report.rejection_reasons else "code_verified",
            prompt_sha256=prompt_hash,
            candidate_sha256=candidate_hash,
            proof_payload=report.to_dict(),
        )

    proof = verify_candidate_against_proof(task, candidate)
    if proof.proof is not None:
        family = _proof_family(proof.proof.proof_type)
        return LocalAdjudicationEvidence(
            task_id=task.id or prompt_hash[:16],
            verifier_family=family,
            verifier_supported=True,
            verifier_accepted=proof.accepted,
            answer_contract_valid=not proof.reason.startswith("answer_contract:"),
            proof_valid=proof.proof.verified,
            proof_unique=proof.proof.unique,
            deterministic_e2b_agreement=proof.accepted,
            normalized_answer_equal=proof.accepted,
            execution_passed=False,
            grounding_passed=False,
            truncation_detected=truncation,
            normalized_answer=proof.canonical_candidate,
            verifier_reason=proof.reason,
            prompt_sha256=prompt_hash,
            candidate_sha256=candidate_hash,
            proof_payload=proof.proof.to_dict(),
        )

    grounded = verify_grounded_candidate(task, candidate)
    if grounded.kind is not None:
        family = _grounded_family(grounded.kind)
        contract_valid = grounded.accepted or not grounded.reason.startswith("answer_contract:")
        lexical_agreement = grounded.metadata and grounded.metadata.get("candidate_label") == grounded.metadata.get("label")
        return LocalAdjudicationEvidence(
            task_id=task.id or prompt_hash[:16],
            verifier_family=family,
            verifier_supported=True,
            verifier_accepted=grounded.accepted,
            answer_contract_valid=contract_valid,
            proof_valid=grounded.accepted,
            proof_unique=grounded.accepted,
            deterministic_e2b_agreement=bool(grounded.accepted and (grounded.kind is not GroundedTaskKind.SENTIMENT or lexical_agreement)),
            normalized_answer_equal=grounded.accepted,
            execution_passed=False,
            grounding_passed=grounded.accepted,
            truncation_detected=truncation,
            normalized_answer=grounded.candidate or candidate.strip(),
            verifier_reason=grounded.reason,
            prompt_sha256=prompt_hash,
            candidate_sha256=candidate_hash,
            proof_payload=grounded.to_dict(),
            span_count=len(grounded.spans),
        )

    contract = apply_answer_contract(task, candidate)
    return LocalAdjudicationEvidence(
        task_id=task.id or prompt_hash[:16],
        verifier_family=VerifierFamily.NONE,
        verifier_supported=False,
        verifier_accepted=False,
        answer_contract_valid=contract.valid,
        proof_valid=False,
        proof_unique=False,
        deterministic_e2b_agreement=False,
        normalized_answer_equal=False,
        execution_passed=False,
        grounding_passed=False,
        truncation_detected=truncation,
        normalized_answer=contract.answer or candidate.strip(),
        verifier_reason="no_registered_verifier",
        prompt_sha256=prompt_hash,
        candidate_sha256=candidate_hash,
    )


def combine_adjudication_features(task_features: FeatureVector, evidence: LocalAdjudicationEvidence) -> FeatureVector:
    response = evidence.to_feature_vector()
    return FeatureVector(names=(*task_features.names, *response.names), values=(*task_features.values, *response.values))


def verifier_registry() -> tuple[dict[str, str], ...]:
    return tuple(item.to_dict() for item in VERIFIER_REGISTRY)


def distribution_shift_score(
    reference: Mapping[str, Any],
    assessments: Sequence[Mapping[str, Any]],
) -> float:
    if not assessments:
        return 1.0
    intent_reference = reference.get("intent_mix")
    score_mean = reference.get("score_mean")
    score_std = reference.get("score_std")
    if not all(isinstance(item, Mapping) for item in (intent_reference, score_mean, score_std)):
        raise ValueError("Distribution reference is malformed.")
    observed_intents: dict[str, int] = {}
    observed_scores: dict[str, list[float]] = {str(name): [] for name in score_mean}
    for assessment in assessments:
        intent = str(assessment.get("intent") or "")
        scores = assessment.get("scores")
        if not intent or not isinstance(scores, Mapping):
            raise ValueError("Assessment batch is malformed.")
        observed_intents[intent] = observed_intents.get(intent, 0) + 1
        for name in observed_scores:
            value = scores.get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("Assessment score batch is malformed.")
            observed_scores[name].append(float(value) / 10.0)
    total = len(assessments)
    intent_names = set(intent_reference) | set(observed_intents)
    total_variation = 0.5 * sum(
        abs(observed_intents.get(name, 0) / total - float(intent_reference.get(name, 0.0)))
        for name in intent_names
    )
    score_shift = 0.0
    for name, values in observed_scores.items():
        observed = sum(values) / len(values)
        baseline = float(score_mean[name])
        scale = max(0.05, float(score_std.get(name, 0.05)))
        score_shift = max(score_shift, min(1.0, abs(observed - baseline) / (3.0 * scale)))
    return max(0.0, min(1.0, max(total_variation, score_shift)))


def _proof_family(proof_type: ProofType) -> VerifierFamily:
    logic = {ProofType.ORDERING, ProofType.FINITE_ASSIGNMENT, ProofType.PROPOSITIONAL, ProofType.QUANTIFIED}
    return VerifierFamily.PROOF_LOGIC if proof_type in logic else VerifierFamily.PROOF_MATH


def _grounded_family(kind: GroundedTaskKind) -> VerifierFamily:
    return {
        GroundedTaskKind.NER: VerifierFamily.GROUNDED_NER,
        GroundedTaskKind.CONTEXT_QA: VerifierFamily.GROUNDED_CONTEXT_QA,
        GroundedTaskKind.SENTIMENT: VerifierFamily.GROUNDED_SENTIMENT,
        GroundedTaskKind.SUMMARY: VerifierFamily.GROUNDED_SUMMARY,
    }[kind]


def _looks_truncated(candidate: str) -> bool:
    stripped = candidate.strip()
    if not stripped:
        return True
    if stripped.count("```") % 2:
        return True
    words = stripped.split()
    return len(words) >= 80 and stripped[-1] not in ".!?}`])\"'"


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split()).strip()


def _mapping(features: FeatureVector) -> dict[str, float]:
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
        raise ValueError(f"Unknown local adjudication feature {name!r}.")
    return derived[name]


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-min(60.0, value)))
    exponential = math.exp(max(-60.0, value))
    return exponential / (1.0 + exponential)


def _probability(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be a probability in [0, 1].")
    return float(value)
