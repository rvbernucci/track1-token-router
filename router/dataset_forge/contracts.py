from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from router.core.contracts import (
    ASSESSMENT_SCHEMA_VERSION,
    SUB_INTENT_TAXONOMY_VERSION,
    TaskAssessment,
)


DATASET_ROW_SCHEMA_VERSION = "assessment-dataset-row-v1"
RATING_SCHEMA_VERSION = "assessment-rating-v1"
GOLD_SCHEMA_VERSION = "assessment-gold-v2"
RUBRIC_VERSION = "assessment-rubric-v2"
RATIONALE_FIELDS = (
    "deterministic_fit",
    "reasoning_demand",
    "knowledge_uncertainty",
    "generation_demand",
    "format_complexity",
)


@dataclass(frozen=True)
class ProviderProvenance:
    provider: str
    model: str
    role: str
    auth_mode: str
    usage_window: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    equivalent_cost_usd: float
    billable_cost_usd: float
    request_id: str
    config_sha256: str

    def __post_init__(self) -> None:
        for name in ("provider", "model", "role", "auth_mode", "usage_window", "request_id", "config_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"ProviderProvenance.{name} must be a non-empty string.")
        for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"ProviderProvenance.{name} must be a non-negative integer.")
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError("ProviderProvenance.total_tokens must equal prompt plus completion tokens.")
        for name in ("equivalent_cost_usd", "billable_cost_usd"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"ProviderProvenance.{name} must be non-negative.")
        if self.provider == "claude_code" and self.billable_cost_usd != 0:
            raise ValueError("Claude Code subscription usage must not be recorded as billable API cost.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "role": self.role,
            "auth_mode": self.auth_mode,
            "usage_window": self.usage_window,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "equivalent_cost_usd": self.equivalent_cost_usd,
            "billable_cost_usd": self.billable_cost_usd,
            "request_id": self.request_id,
            "config_sha256": self.config_sha256,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ProviderProvenance":
        _exact_keys(payload, set(cls.__dataclass_fields__), "ProviderProvenance")
        return cls(**{name: payload[name] for name in cls.__dataclass_fields__})


@dataclass(frozen=True)
class DatasetProposal:
    id: str
    target_id: str
    parent_id: str | None
    task_text: str
    assessment: TaskAssessment
    rationales: tuple[tuple[str, str], ...]
    source: str
    template_family: str
    mutation_lineage: str
    language: str
    mutation_kind: str
    boundary_dimension: str | None
    boundary_anchor: int | None
    provenance: ProviderProvenance
    content_sha256: str
    created_at: str
    schema_version: str = DATASET_ROW_SCHEMA_VERSION
    assessment_schema_version: str = ASSESSMENT_SCHEMA_VERSION
    taxonomy_version: str = SUB_INTENT_TAXONOMY_VERSION
    rubric_version: str = RUBRIC_VERSION

    def __post_init__(self) -> None:
        for name in (
            "id",
            "target_id",
            "task_text",
            "source",
            "template_family",
            "mutation_lineage",
            "language",
            "mutation_kind",
            "content_sha256",
            "created_at",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"DatasetProposal.{name} must be a non-empty string.")
        if self.parent_id is not None and not isinstance(self.parent_id, str):
            raise ValueError("DatasetProposal.parent_id must be a string or null.")
        rationale_map = dict(self.rationales)
        if (
            len(self.rationales) != len(RATIONALE_FIELDS)
            or set(rationale_map) != set(RATIONALE_FIELDS)
            or any(not isinstance(value, str) or not value.strip() for value in rationale_map.values())
        ):
            raise ValueError("DatasetProposal requires one non-empty rationale per assessment score.")
        if self.boundary_dimension is not None and self.boundary_dimension not in RATIONALE_FIELDS:
            raise ValueError("DatasetProposal.boundary_dimension must name an assessment score or be null.")
        if self.boundary_anchor is not None and self.boundary_anchor not in {0, 2, 5, 8, 10}:
            raise ValueError("DatasetProposal.boundary_anchor must be one of 0, 2, 5, 8, 10 or null.")
        if (
            self.boundary_dimension is not None
            and self.boundary_anchor is not None
            and getattr(self.assessment.scores, self.boundary_dimension) != self.boundary_anchor
        ):
            raise ValueError("DatasetProposal assessment does not match its declared boundary anchor.")
        if self.content_sha256 != content_sha256(self.task_text):
            raise ValueError("DatasetProposal.content_sha256 does not match task_text.")
        if self.schema_version != DATASET_ROW_SCHEMA_VERSION:
            raise ValueError(f"Unsupported dataset row schema: {self.schema_version!r}.")
        if self.assessment_schema_version != ASSESSMENT_SCHEMA_VERSION:
            raise ValueError(f"Unsupported assessment schema: {self.assessment_schema_version!r}.")
        if self.taxonomy_version != SUB_INTENT_TAXONOMY_VERSION:
            raise ValueError(f"Unsupported taxonomy: {self.taxonomy_version!r}.")
        if self.rubric_version != RUBRIC_VERSION:
            raise ValueError(f"Unsupported rubric: {self.rubric_version!r}.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "target_id": self.target_id,
            "parent_id": self.parent_id,
            "task_text": self.task_text,
            "assessment": self.assessment.to_dict(),
            "rationales": dict(self.rationales),
            "source": self.source,
            "template_family": self.template_family,
            "mutation_lineage": self.mutation_lineage,
            "language": self.language,
            "mutation_kind": self.mutation_kind,
            "boundary_dimension": self.boundary_dimension,
            "boundary_anchor": self.boundary_anchor,
            "provenance": self.provenance.to_dict(),
            "content_sha256": self.content_sha256,
            "created_at": self.created_at,
            "assessment_schema_version": self.assessment_schema_version,
            "taxonomy_version": self.taxonomy_version,
            "rubric_version": self.rubric_version,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "DatasetProposal":
        _exact_keys(payload, set(_proposal_fields()), "DatasetProposal")
        assessment = payload["assessment"]
        rationales = payload["rationales"]
        provenance = payload["provenance"]
        if not isinstance(assessment, Mapping) or not isinstance(rationales, Mapping) or not isinstance(provenance, Mapping):
            raise ValueError("DatasetProposal nested contracts must be objects.")
        return cls(
            id=_string(payload["id"], "DatasetProposal.id"),
            target_id=_string(payload["target_id"], "DatasetProposal.target_id"),
            parent_id=_optional_string(payload["parent_id"], "DatasetProposal.parent_id"),
            task_text=_string(payload["task_text"], "DatasetProposal.task_text"),
            assessment=TaskAssessment.from_mapping(assessment),
            rationales=tuple(sorted((_string(key, "rationale key"), _string(value, f"rationale.{key}")) for key, value in rationales.items())),
            source=_string(payload["source"], "DatasetProposal.source"),
            template_family=_string(payload["template_family"], "DatasetProposal.template_family"),
            mutation_lineage=_string(payload["mutation_lineage"], "DatasetProposal.mutation_lineage"),
            language=_string(payload["language"], "DatasetProposal.language"),
            mutation_kind=_string(payload["mutation_kind"], "DatasetProposal.mutation_kind"),
            boundary_dimension=_optional_string(payload["boundary_dimension"], "DatasetProposal.boundary_dimension"),
            boundary_anchor=payload["boundary_anchor"],
            provenance=ProviderProvenance.from_mapping(provenance),
            content_sha256=_string(payload["content_sha256"], "DatasetProposal.content_sha256"),
            created_at=_string(payload["created_at"], "DatasetProposal.created_at"),
            schema_version=_string(payload["schema_version"], "DatasetProposal.schema_version"),
            assessment_schema_version=_string(
                payload["assessment_schema_version"], "DatasetProposal.assessment_schema_version"
            ),
            taxonomy_version=_string(payload["taxonomy_version"], "DatasetProposal.taxonomy_version"),
            rubric_version=_string(payload["rubric_version"], "DatasetProposal.rubric_version"),
        )


@dataclass(frozen=True)
class AssessmentRating:
    id: str
    example_id: str
    rater_id: str
    assessment: TaskAssessment
    rationales: tuple[tuple[str, str], ...]
    provenance: ProviderProvenance
    created_at: str
    schema_version: str = RATING_SCHEMA_VERSION
    rubric_version: str = RUBRIC_VERSION

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value for value in (self.id, self.example_id, self.rater_id, self.created_at)):
            raise ValueError("AssessmentRating identifiers and created_at are required.")
        if set(dict(self.rationales)) != set(RATIONALE_FIELDS):
            raise ValueError("AssessmentRating requires one rationale per score.")
        if self.schema_version != RATING_SCHEMA_VERSION or self.rubric_version != RUBRIC_VERSION:
            raise ValueError("Unsupported AssessmentRating version.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "example_id": self.example_id,
            "rater_id": self.rater_id,
            "assessment": self.assessment.to_dict(),
            "rationales": dict(self.rationales),
            "provenance": self.provenance.to_dict(),
            "created_at": self.created_at,
            "rubric_version": self.rubric_version,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "AssessmentRating":
        _exact_keys(payload, set(_rating_fields()), "AssessmentRating")
        return cls(
            id=_string(payload["id"], "AssessmentRating.id"),
            example_id=_string(payload["example_id"], "AssessmentRating.example_id"),
            rater_id=_string(payload["rater_id"], "AssessmentRating.rater_id"),
            assessment=TaskAssessment.from_mapping(_mapping(payload["assessment"], "AssessmentRating.assessment")),
            rationales=_rationales(payload["rationales"]),
            provenance=ProviderProvenance.from_mapping(_mapping(payload["provenance"], "AssessmentRating.provenance")),
            created_at=_string(payload["created_at"], "AssessmentRating.created_at"),
            schema_version=_string(payload["schema_version"], "AssessmentRating.schema_version"),
            rubric_version=_string(payload["rubric_version"], "AssessmentRating.rubric_version"),
        )


@dataclass(frozen=True)
class GoldAssessment:
    id: str
    example_id: str
    assessment: TaskAssessment
    rating_ids: tuple[str, ...]
    adjudication_status: str
    intent_agreement: float
    max_score_spread: int
    adjudicator: str
    created_at: str
    revision: int = 1
    supersedes_id: str | None = None
    schema_version: str = GOLD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value
            for value in (self.id, self.example_id, self.adjudicator, self.created_at)
        ):
            raise ValueError("GoldAssessment identifiers, adjudicator and created_at are required.")
        if len(set(self.rating_ids)) < 2:
            raise ValueError("GoldAssessment requires at least two independent ratings.")
        if self.adjudication_status not in {"accepted", "needs_review", "rejected"}:
            raise ValueError("Unknown GoldAssessment.adjudication_status.")
        if not 0 <= self.intent_agreement <= 1 or not 0 <= self.max_score_spread <= 10:
            raise ValueError("GoldAssessment agreement metrics are out of range.")
        if self.schema_version != GOLD_SCHEMA_VERSION:
            raise ValueError(f"Unsupported gold schema: {self.schema_version!r}.")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision < 1:
            raise ValueError("GoldAssessment.revision must be a positive integer.")
        if self.supersedes_id is not None and not isinstance(self.supersedes_id, str):
            raise ValueError("GoldAssessment.supersedes_id must be a string or null.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "example_id": self.example_id,
            "assessment": self.assessment.to_dict(),
            "rating_ids": list(self.rating_ids),
            "adjudication_status": self.adjudication_status,
            "intent_agreement": self.intent_agreement,
            "max_score_spread": self.max_score_spread,
            "adjudicator": self.adjudicator,
            "created_at": self.created_at,
            "revision": self.revision,
            "supersedes_id": self.supersedes_id,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "GoldAssessment":
        if payload.get("schema_version") == "assessment-gold-v1":
            payload = {**payload, "schema_version": GOLD_SCHEMA_VERSION, "revision": 1, "supersedes_id": None}
        expected = {
            "schema_version",
            "id",
            "example_id",
            "assessment",
            "rating_ids",
            "adjudication_status",
            "intent_agreement",
            "max_score_spread",
            "adjudicator",
            "created_at",
            "revision",
            "supersedes_id",
        }
        _exact_keys(payload, expected, "GoldAssessment")
        rating_ids = payload["rating_ids"]
        if not isinstance(rating_ids, list):
            raise ValueError("GoldAssessment.rating_ids must be an array.")
        return cls(
            schema_version=_string(payload["schema_version"], "GoldAssessment.schema_version"),
            id=_string(payload["id"], "GoldAssessment.id"),
            example_id=_string(payload["example_id"], "GoldAssessment.example_id"),
            assessment=TaskAssessment.from_mapping(_mapping(payload["assessment"], "GoldAssessment.assessment")),
            rating_ids=tuple(_string(item, "GoldAssessment.rating_ids[]") for item in rating_ids),
            adjudication_status=_string(payload["adjudication_status"], "GoldAssessment.adjudication_status"),
            intent_agreement=payload["intent_agreement"],
            max_score_spread=payload["max_score_spread"],
            adjudicator=_string(payload["adjudicator"], "GoldAssessment.adjudicator"),
            created_at=_string(payload["created_at"], "GoldAssessment.created_at"),
            revision=payload["revision"],
            supersedes_id=_optional_string(payload["supersedes_id"], "GoldAssessment.supersedes_id"),
        )


def content_sha256(text: str) -> str:
    normalized = " ".join(text.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def config_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rationales_from_mapping(payload: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    return _rationales(payload)


def _rationales(value: Any) -> tuple[tuple[str, str], ...]:
    payload = _mapping(value, "rationales")
    if set(payload) != set(RATIONALE_FIELDS):
        raise ValueError(f"rationales must contain exactly {list(RATIONALE_FIELDS)}.")
    return tuple(sorted((key, _string(payload[key], f"rationales.{key}")) for key in payload))


def _mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object.")
    return value


def _string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _string(value, field_name)


def _exact_keys(payload: Mapping[str, Any], expected: set[str], contract: str) -> None:
    actual = set(payload)
    if actual != expected:
        raise ValueError(
            f"{contract} fields mismatch: missing={sorted(expected - actual)}, additional={sorted(actual - expected)}."
        )


def _proposal_fields() -> tuple[str, ...]:
    return (
        "schema_version",
        "id",
        "target_id",
        "parent_id",
        "task_text",
        "assessment",
        "rationales",
        "source",
        "template_family",
        "mutation_lineage",
        "language",
        "mutation_kind",
        "boundary_dimension",
        "boundary_anchor",
        "provenance",
        "content_sha256",
        "created_at",
        "assessment_schema_version",
        "taxonomy_version",
        "rubric_version",
    )


def _rating_fields() -> tuple[str, ...]:
    return (
        "schema_version",
        "id",
        "example_id",
        "rater_id",
        "assessment",
        "rationales",
        "provenance",
        "created_at",
        "rubric_version",
    )
