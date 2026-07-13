from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from router.core.contracts import Intent, TaskAssessment, TaskEnvelope
from router.orchestration.e2b_mechanical_features import extract_e2b_mechanical_features
from router.orchestration.final_validator import AnswerContractResult, apply_answer_contract


SCHEMA_VERSION = "e2b-extra-trees-code-debug-v1"
_ALLOWED_INTENT = Intent.CODE_DEBUGGING.value
_SCORE_NAMES = (
    "deterministic_fit",
    "reasoning_demand",
    "knowledge_uncertainty",
    "generation_demand",
    "format_complexity",
)
_INTENTS = tuple(intent.value for intent in Intent)
_CONTRACT_KINDS = ("free_text", "label", "number", "list", "json", "code")
_CONSTRAINT = re.compile(
    r"\b(?:only|exactly|must|maximum|minimum|no more than|without)\b",
    re.IGNORECASE,
)
_HEX_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class E2BExtraTreesDecision:
    probability: float
    accepted: bool
    reason: str
    answer: str = ""
    contract_valid: bool = False


@dataclass(frozen=True)
class _Leaf:
    probability: float


@dataclass(frozen=True)
class _Branch:
    feature_index: int
    threshold: float
    left: "_Node"
    right: "_Node"


_Node = _Leaf | _Branch


@dataclass(frozen=True)
class E2BExtraTreesGate:
    enabled: bool
    threshold: float
    feature_names: tuple[str, ...]
    trees: tuple[_Node, ...]
    artifact_sha256: str

    @classmethod
    def load(cls, path: Path, *, expected_sha256: str) -> "E2BExtraTreesGate":
        if not isinstance(expected_sha256, str) or not _HEX_SHA256.fullmatch(expected_sha256):
            raise ValueError("A lowercase SHA-256 pin is required for the E2B Extra Trees policy.")
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected_sha256:
            raise ValueError("E2B Extra Trees policy SHA-256 mismatch.")
        payload = json.loads(raw)
        if not isinstance(payload, Mapping) or payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("E2B Extra Trees policy schema is invalid.")
        if payload.get("allowed_intent") != _ALLOWED_INTENT:
            raise ValueError("E2B Extra Trees policy must be restricted to code_debugging.")
        enabled = payload.get("default_enabled")
        if not isinstance(enabled, bool):
            raise ValueError("E2B Extra Trees default_enabled must be a boolean.")
        threshold = _probability(payload.get("threshold"), "threshold")
        names = payload.get("feature_names")
        if (
            not isinstance(names, list)
            or not names
            or len(names) != len(set(names))
            or any(not isinstance(name, str) or not name for name in names)
        ):
            raise ValueError("E2B Extra Trees feature_names must be unique non-empty strings.")
        raw_trees = payload.get("trees")
        if not isinstance(raw_trees, list) or not raw_trees or len(raw_trees) > 512:
            raise ValueError("E2B Extra Trees policy requires between 1 and 512 trees.")
        trees = tuple(_parse_node(node, len(names), depth=0, budget=[0]) for node in raw_trees)
        return cls(enabled, threshold, tuple(names), trees, digest)

    def should_probe(self, intent: Intent | str) -> bool:
        value = intent.value if isinstance(intent, Intent) else intent
        return self.enabled and value == _ALLOWED_INTENT

    def evaluate(
        self,
        task: TaskEnvelope,
        raw_assessment: TaskAssessment | Mapping[str, Any],
        answer: str,
    ) -> E2BExtraTreesDecision:
        try:
            if not self.enabled:
                return E2BExtraTreesDecision(0.0, False, "extra_trees_disabled")
            if not isinstance(task, TaskEnvelope) or not task.input_text.strip():
                return E2BExtraTreesDecision(0.0, False, "invalid_task")
            assessment = _assessment(raw_assessment)
            if not self.should_probe(assessment.intent):
                return E2BExtraTreesDecision(0.0, False, "intent_not_eligible")
            if not isinstance(answer, str):
                return E2BExtraTreesDecision(0.0, False, "invalid_answer")
            contract = apply_answer_contract(task, answer)
            features = _runtime_features(task, assessment, contract)
            vector = tuple(_feature(features, name) for name in self.feature_names)
            probability = sum(_score(tree, vector) for tree in self.trees) / len(self.trees)
            if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
                return E2BExtraTreesDecision(0.0, False, "non_finite_probability")
            if not contract.valid:
                return E2BExtraTreesDecision(
                    probability,
                    False,
                    f"answer_contract_rejected:{contract.reason}",
                    contract_valid=False,
                )
            if probability < self.threshold:
                return E2BExtraTreesDecision(
                    probability,
                    False,
                    "extra_trees_below_threshold",
                    contract_valid=True,
                )
            return E2BExtraTreesDecision(
                probability,
                True,
                "extra_trees_code_debug_accept",
                answer=contract.answer,
                contract_valid=True,
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            return E2BExtraTreesDecision(0.0, False, "extra_trees_feature_failure")


def _assessment(raw: TaskAssessment | Mapping[str, Any]) -> TaskAssessment:
    if isinstance(raw, TaskAssessment):
        return raw
    if not isinstance(raw, Mapping):
        raise ValueError("FunctionGemma assessment must be an object.")
    return TaskAssessment.from_mapping(raw)


def _runtime_features(
    task: TaskEnvelope,
    assessment: TaskAssessment,
    contract: AnswerContractResult,
) -> dict[str, float]:
    prompt = task.input_text
    values = {
        f"fg.{name}": float(value) / 10.0
        for name, value in assessment.scores.to_dict().items()
    }
    values.update(extract_e2b_mechanical_features(prompt).to_dict()["features"])
    kind = contract.contract.kind.value
    values.update(
        {
            "contract.valid": float(contract.valid),
            "contract.strict": float(contract.contract.strict),
            "contract.changed": float(contract.changed),
            "contract.exact_items": float(contract.contract.exact_items or 0),
            "contract.exact_sentences": float(contract.contract.exact_sentences or 0),
            "contract.max_words_log": math.log1p(float(contract.contract.max_words or 0)),
            **{f"contract.kind.{name}": float(kind == name) for name in _CONTRACT_KINDS},
        }
    )
    # The promoted cohort had no registered deterministic verifier. The gate does not
    # invent proof evidence that is absent from its explicit runtime inputs.
    values.update(
        {
            "proof.supported": 0.0,
            "proof.unique": 0.0,
            "proof.valid": 0.0,
            "proof.registered": 0.0,
        }
    )
    values.update({f"intent.{name}": float(assessment.intent.value == name) for name in _INTENTS})
    values["assessment.missing"] = 0.0
    values["prompt.char_log"] = math.log1p(len(prompt))
    values["prompt.line_log"] = math.log1p(prompt.count("\n") + 1)
    values["prompt.constraint_count"] = float(len(_CONSTRAINT.findall(prompt)))
    return values


def _feature(values: Mapping[str, float], name: str) -> float:
    value = values[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid runtime feature {name!r}.")
    return float(value)


def _score(node: _Node, values: tuple[float, ...]) -> float:
    while isinstance(node, _Branch):
        node = node.left if values[node.feature_index] <= node.threshold else node.right
    return node.probability


def _parse_node(payload: Any, dimensions: int, *, depth: int, budget: list[int]) -> _Node:
    budget[0] += 1
    if depth > 16 or budget[0] > 100_000 or not isinstance(payload, Mapping):
        raise ValueError("E2B Extra Trees node limit exceeded or node is invalid.")
    if set(payload) == {"p"}:
        return _Leaf(_probability(payload["p"], "tree leaf probability"))
    if set(payload) != {"p", "f", "t", "l", "r"}:
        raise ValueError("E2B Extra Trees branch schema is invalid.")
    _probability(payload["p"], "tree branch probability")
    feature = payload["f"]
    threshold = payload["t"]
    if isinstance(feature, bool) or not isinstance(feature, int) or not 0 <= feature < dimensions:
        raise ValueError("E2B Extra Trees feature index is invalid.")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold):
        raise ValueError("E2B Extra Trees split threshold is invalid.")
    return _Branch(
        feature,
        float(threshold),
        _parse_node(payload["l"], dimensions, depth=depth + 1, budget=budget),
        _parse_node(payload["r"], dimensions, depth=depth + 1, budget=budget),
    )


def _probability(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be a finite probability.")
    return float(value)
