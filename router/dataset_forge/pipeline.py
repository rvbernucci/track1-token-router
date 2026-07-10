from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

from router.core.contracts import AssessmentScores, Intent, TaskAssessment
from router.dataset_forge.contracts import (
    AssessmentRating,
    DatasetProposal,
    ProviderProvenance,
    config_sha256,
    content_sha256,
    rationales_from_mapping,
    stable_id,
    utc_now,
)
from router.dataset_forge.dedup import deduplicate
from router.dataset_forge.planner import GenerationTarget
from router.dataset_forge.prompts import generation_prompt, rating_prompt
from router.dataset_forge.providers import (
    FireworksDatasetProvider,
    ProviderBudgetExceeded,
    ProviderError,
    ProviderInvocation,
    ProviderQuotaExhausted,
    generation_response_schema,
    rating_response_schema,
)
from router.dataset_forge.storage import AppendOnlyJsonl, AtomicCheckpoint


class DatasetProvider(Protocol):
    def invoke(self, *, prompt: str, response_schema: Mapping[str, Any], role: str) -> ProviderInvocation:
        ...


@dataclass(frozen=True)
class ForgePaths:
    root: Path

    @property
    def raw_proposals(self) -> Path:
        return self.root / "raw" / "proposals.jsonl"

    @property
    def validated_proposals(self) -> Path:
        return self.root / "validated" / "proposals.jsonl"

    @property
    def deduped_proposals(self) -> Path:
        return self.root / "deduped" / "proposals.jsonl"

    @property
    def dedup_decisions(self) -> Path:
        return self.root / "deduped" / "decisions.jsonl"

    @property
    def ratings(self) -> Path:
        return self.root / "ratings" / "ratings.jsonl"

    @property
    def manual_reviews(self) -> Path:
        return self.root / "adjudicated" / "manual-reviews.jsonl"

    @property
    def failures(self) -> Path:
        return self.root / "state" / "failures.jsonl"

    @property
    def provider_responses(self) -> Path:
        return self.root / "raw" / "provider-responses.jsonl"

    @property
    def checkpoint(self) -> Path:
        return self.root / "state" / "checkpoint.json"


@dataclass(frozen=True)
class BatchWork:
    index: int
    provider_name: str
    targets: tuple[GenerationTarget, ...]


@dataclass(frozen=True)
class BatchResult:
    work: BatchWork
    invocation: ProviderInvocation | None
    error: str = ""
    quota_exhausted: bool = False


class BudgetLedger:
    def __init__(self, limit_usd: float, *, spent_usd: float = 0.0) -> None:
        if limit_usd < 0 or spent_usd < 0 or spent_usd > limit_usd:
            raise ValueError("Invalid Fireworks budget ledger.")
        self.limit_usd = limit_usd
        self.spent_usd = spent_usd
        self.reserved_usd = 0.0
        self._lock = threading.Lock()

    def reserve(self, estimate_usd: float) -> None:
        with self._lock:
            if self.spent_usd + self.reserved_usd + estimate_usd > self.limit_usd + 1e-12:
                raise ProviderBudgetExceeded(
                    f"Fireworks budget would exceed ${self.limit_usd:.6f}; "
                    f"spent=${self.spent_usd:.6f}, reserved=${self.reserved_usd:.6f}, request=${estimate_usd:.6f}."
                )
            self.reserved_usd += estimate_usd

    def reconcile(self, estimate_usd: float, actual_usd: float) -> None:
        with self._lock:
            self.reserved_usd = max(0.0, self.reserved_usd - estimate_usd)
            if self.spent_usd + actual_usd > self.limit_usd + 1e-12:
                raise ProviderBudgetExceeded("Fireworks actual cost exceeded the configured budget.")
            self.spent_usd += actual_usd

    def release(self, estimate_usd: float) -> None:
        with self._lock:
            self.reserved_usd = max(0.0, self.reserved_usd - estimate_usd)


def generate(
    *,
    targets: list[GenerationTarget],
    providers: Mapping[str, DatasetProvider],
    paths: ForgePaths,
    batch_size: int,
    max_workers: int,
    fireworks_budget_usd: float,
    fallback_provider: str | None = None,
    provider_order: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    if not providers:
        raise ValueError("At least one dataset provider is required.")
    if batch_size < 1 or max_workers < 1:
        raise ValueError("batch_size and max_workers must be positive.")
    checkpoint_store = AtomicCheckpoint(paths.checkpoint)
    checkpoint = checkpoint_store.load()
    completed = set(checkpoint.get("completed_target_ids") or [])
    pending = [target for target in targets if target.id not in completed]
    scheduled_providers = provider_order or tuple(providers)
    if not scheduled_providers or any(name not in providers for name in scheduled_providers):
        raise ValueError("provider_order must reference configured providers.")
    works = _batch_work(pending, scheduled_providers, batch_size)
    ledger = BudgetLedger(
        fireworks_budget_usd,
        spent_usd=float(checkpoint.get("fireworks_billable_usd") or 0.0),
    )
    proposals_store = AppendOnlyJsonl(paths.raw_proposals)
    responses_store = AppendOnlyJsonl(paths.provider_responses)
    failures_store = AppendOnlyJsonl(paths.failures)
    written = 0
    paused = False
    handoffs = int(checkpoint.get("provider_handoffs") or 0)
    batches_completed = int(checkpoint.get("batches_completed") or 0)

    for wave_start in range(0, len(works), max_workers):
        wave = works[wave_start : wave_start + max_workers]
        with ThreadPoolExecutor(max_workers=len(wave), thread_name_prefix="dataset-forge") as executor:
            futures = [
                executor.submit(_run_generation_batch, work, providers[work.provider_name], ledger)
                for work in wave
            ]
            results = [future.result() for future in futures]

        for result in sorted(results, key=lambda item: item.work.index):
            if result.invocation is None and result.quota_exhausted and fallback_provider:
                fallback = providers.get(fallback_provider)
                if fallback is None:
                    raise ValueError(f"Fallback provider {fallback_provider!r} is not configured.")
                fallback_work = BatchWork(result.work.index, fallback_provider, result.work.targets)
                result = _run_generation_batch(fallback_work, fallback, ledger)
                handoffs += 1

            if result.invocation is None:
                paused = paused or result.quota_exhausted
                _append_failure(failures_store, result.work, result.error, retriable=result.quota_exhausted)
                continue

            responses_store.append_unique(
                {
                    "id": result.invocation.provenance.request_id,
                    "stage": "generate",
                    "provider": result.work.provider_name,
                    "target_ids": [target.id for target in result.work.targets],
                    "payload": result.invocation.payload,
                    "provenance": result.invocation.provenance.to_dict(),
                    "created_at": utc_now(),
                }
            )
            try:
                proposals = _proposals_from_invocation(result.work, result.invocation)
            except (TypeError, ValueError) as exc:
                _append_failure(failures_store, result.work, f"invalid_provider_payload: {exc}", retriable=True)
                continue
            for proposal in proposals:
                if proposals_store.append_unique(proposal.to_dict()):
                    written += 1
                completed.add(proposal.target_id)
            batches_completed += 1
            checkpoint_store.save(
                {
                    **checkpoint,
                    "completed_target_ids": sorted(completed),
                    "fireworks_billable_usd": round(ledger.spent_usd, 10),
                    "provider_handoffs": handoffs,
                    "batches_completed": batches_completed,
                    "last_batch_index": result.work.index,
                    "updated_at": utc_now(),
                }
            )

    return {
        "targets": len(targets),
        "pending_at_start": len(pending),
        "completed": len(completed),
        "written": written,
        "paused_for_quota": paused,
        "fireworks_billable_usd": round(ledger.spent_usd, 10),
        "provider_handoffs": handoffs,
        "batches_completed": batches_completed,
    }


def validate(paths: ForgePaths) -> dict[str, int]:
    source = AppendOnlyJsonl(paths.raw_proposals).read_all()
    destination = AppendOnlyJsonl(paths.validated_proposals)
    failures = AppendOnlyJsonl(paths.failures)
    valid = 0
    invalid = 0
    for index, payload in enumerate(source):
        try:
            proposal = DatasetProposal.from_mapping(payload)
        except (TypeError, ValueError) as exc:
            invalid += 1
            failure_id = stable_id("failure", "validation", str(index), str(payload.get("id") or "missing"))
            failures.append_unique(
                {
                    "id": failure_id,
                    "stage": "validate",
                    "record_id": payload.get("id"),
                    "error": str(exc),
                    "retriable": False,
                    "created_at": utc_now(),
                }
            )
            continue
        if destination.append_unique(proposal.to_dict()):
            valid += 1
    return {"input": len(source), "valid_written": valid, "invalid": invalid}


def deduplicate_validated(paths: ForgePaths) -> dict[str, int]:
    proposals = [
        DatasetProposal.from_mapping(payload)
        for payload in AppendOnlyJsonl(paths.validated_proposals).read_all()
    ]
    accepted, decisions = deduplicate(proposals)
    accepted_store = AppendOnlyJsonl(paths.deduped_proposals)
    decision_store = AppendOnlyJsonl(paths.dedup_decisions)
    written = sum(1 for proposal in accepted if accepted_store.append_unique(proposal.to_dict()))
    decision_written = sum(1 for decision in decisions if decision_store.append_unique(decision.to_dict()))
    return {
        "input": len(proposals),
        "accepted": len(accepted),
        "duplicates": len(proposals) - len(accepted),
        "accepted_written": written,
        "decisions_written": decision_written,
    }


def rate(
    *,
    provider_name: str,
    provider: DatasetProvider,
    paths: ForgePaths,
    batch_size: int,
    fireworks_budget_usd: float,
    example_ids: set[str] | None = None,
) -> dict[str, Any]:
    proposals = [
        DatasetProposal.from_mapping(payload)
        for payload in AppendOnlyJsonl(paths.deduped_proposals).read_all()
    ]
    ratings_store = AppendOnlyJsonl(paths.ratings)
    existing = [AssessmentRating.from_mapping(payload) for payload in ratings_store.read_all()]
    provider_model = getattr(provider, "model", "unknown")
    rater_id = f"{provider_name}:{provider_model}"
    already_rated = {rating.example_id for rating in existing if rating.rater_id == rater_id}
    pending = [
        proposal
        for proposal in proposals
        if proposal.id not in already_rated and (example_ids is None or proposal.id in example_ids)
    ]
    ledger = BudgetLedger(fireworks_budget_usd)
    written = 0
    quota_exhausted = False
    for batch in _chunks(pending, batch_size):
        prompt = rating_prompt([proposal.to_dict() for proposal in batch], rater_id=rater_id)
        estimate = _reserve_if_fireworks(provider, prompt, ledger)
        try:
            invocation = provider.invoke(
                prompt=prompt,
                response_schema=rating_response_schema(len(batch)),
                role="rater",
            )
        except ProviderQuotaExhausted:
            ledger.release(estimate)
            quota_exhausted = True
            break
        except ProviderError:
            ledger.release(estimate)
            raise
        _reconcile_if_fireworks(provider, invocation.provenance, estimate, ledger)
        ratings = _ratings_from_invocation(batch, invocation, rater_id)
        for rating in ratings:
            if ratings_store.append_unique(rating.to_dict()):
                written += 1
    return {
        "rater_id": rater_id,
        "input": len(proposals),
        "pending_at_start": len(pending),
        "written": written,
        "quota_exhausted": quota_exhausted,
        "fireworks_billable_usd": round(ledger.spent_usd, 10),
    }


def rate_target_contract(paths: ForgePaths) -> dict[str, Any]:
    """Materialize the labels that the generation target already proves mechanically."""
    proposals = [
        DatasetProposal.from_mapping(payload)
        for payload in AppendOnlyJsonl(paths.deduped_proposals).read_all()
    ]
    ratings_store = AppendOnlyJsonl(paths.ratings)
    rater_id = "mechanical:target-contract-v1"
    existing = [AssessmentRating.from_mapping(payload) for payload in ratings_store.read_all()]
    already_rated = {rating.example_id for rating in existing if rating.rater_id == rater_id}
    written = 0
    for proposal in proposals:
        if proposal.id in already_rated:
            continue
        request_id = stable_id("target-contract", proposal.target_id, proposal.content_sha256)
        provenance = ProviderProvenance(
            provider="mechanical",
            model="target-contract-v1",
            role="rater",
            auth_mode="none",
            usage_window="offline",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            equivalent_cost_usd=0.0,
            billable_cost_usd=0.0,
            request_id=request_id,
            config_sha256=config_sha256(
                {
                    "intent": proposal.assessment.intent.value,
                    "sub_intent": proposal.assessment.sub_intent,
                    "boundary_dimension": proposal.boundary_dimension,
                    "boundary_anchor": proposal.boundary_anchor,
                }
            ),
        )
        rationales = dict(proposal.rationales)
        if proposal.boundary_dimension is not None:
            rationales[proposal.boundary_dimension] = (
                f"Generation target mechanically requires anchor {proposal.boundary_anchor}."
            )
        rating = AssessmentRating(
            id=stable_id("rating", proposal.id, rater_id, request_id),
            example_id=proposal.id,
            rater_id=rater_id,
            assessment=proposal.assessment,
            rationales=tuple(sorted(rationales.items())),
            provenance=provenance,
            created_at=utc_now(),
        )
        if ratings_store.append_unique(rating.to_dict()):
            written += 1
    return {
        "rater_id": rater_id,
        "input": len(proposals),
        "pending_at_start": len(proposals) - len(already_rated),
        "written": written,
        "fireworks_billable_usd": 0.0,
    }


def _run_generation_batch(work: BatchWork, provider: DatasetProvider, ledger: BudgetLedger) -> BatchResult:
    prompt = generation_prompt(list(work.targets))
    estimate = _reserve_if_fireworks(provider, prompt, ledger)
    try:
        invocation = provider.invoke(
            prompt=prompt,
            response_schema=generation_response_schema(len(work.targets)),
            role="generator",
        )
    except ProviderQuotaExhausted as exc:
        ledger.release(estimate)
        return BatchResult(work, None, str(exc), quota_exhausted=True)
    except (ProviderBudgetExceeded, ProviderError) as exc:
        ledger.release(estimate)
        return BatchResult(work, None, str(exc), quota_exhausted=False)
    try:
        _reconcile_if_fireworks(provider, invocation.provenance, estimate, ledger)
    except ProviderBudgetExceeded as exc:
        return BatchResult(work, None, str(exc), quota_exhausted=False)
    return BatchResult(work, invocation)


def _reserve_if_fireworks(provider: DatasetProvider, prompt: str, ledger: BudgetLedger) -> float:
    if not isinstance(provider, FireworksDatasetProvider):
        return 0.0
    estimate = provider.estimate_upper_bound_usd(prompt)
    ledger.reserve(estimate)
    return estimate


def _reconcile_if_fireworks(
    provider: DatasetProvider,
    provenance: ProviderProvenance,
    estimate: float,
    ledger: BudgetLedger,
) -> None:
    if isinstance(provider, FireworksDatasetProvider):
        ledger.reconcile(estimate, provenance.billable_cost_usd)


def _proposals_from_invocation(work: BatchWork, invocation: ProviderInvocation) -> list[DatasetProposal]:
    items = invocation.payload.get("items")
    if not isinstance(items, list) or len(items) != len(work.targets):
        raise ValueError("Provider must return exactly one item per generation target.")
    target_by_id = {target.id: target for target in work.targets}
    proposals: list[DatasetProposal] = []
    seen: set[str] = set()
    expected_item_keys = {
        "target_id",
        "task_text",
        "assessment",
        "rationales",
        "template_family",
        "mutation_lineage",
        "language",
        "mutation_kind",
        "boundary_dimension",
        "boundary_anchor",
        "parent_id",
    }
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("Generation item must be an object.")
        if set(item) != expected_item_keys:
            raise ValueError(
                f"Generation item fields mismatch: missing={sorted(expected_item_keys - set(item))}, "
                f"additional={sorted(set(item) - expected_item_keys)}."
            )
        target_id = item.get("target_id")
        if not isinstance(target_id, str) or target_id not in target_by_id or target_id in seen:
            raise ValueError(f"Unknown or duplicate target_id {target_id!r}.")
        target = target_by_id[target_id]
        assessment_payload = item.get("assessment")
        rationales_payload = item.get("rationales")
        if not isinstance(assessment_payload, Mapping) or not isinstance(rationales_payload, Mapping):
            raise ValueError("Generation assessment and rationales must be objects.")
        assessment = TaskAssessment.from_mapping(assessment_payload)
        if assessment.intent is not target.intent or assessment.sub_intent != target.sub_intent:
            raise ValueError(f"Target taxonomy mismatch for {target_id}.")
        if item.get("boundary_dimension") != target.boundary_dimension:
            raise ValueError(f"Target boundary dimension mismatch for {target_id}.")
        if item.get("boundary_anchor") != target.boundary_anchor:
            raise ValueError(f"Target boundary anchor mismatch for {target_id}.")
        if getattr(assessment.scores, target.boundary_dimension) != target.boundary_anchor:
            raise ValueError(f"Assessment did not honor boundary anchor for {target_id}.")
        if item.get("mutation_lineage") != target.lineage_id:
            raise ValueError(f"Mutation lineage mismatch for {target_id}.")
        if item.get("language") != target.language or item.get("mutation_kind") != target.mutation_kind:
            raise ValueError(f"Language or mutation mismatch for {target_id}.")
        if item.get("parent_id") != target.parent_target_id:
            raise ValueError(f"Parent lineage mismatch for {target_id}.")
        task_text = _required_string(item.get("task_text"), "task_text")
        proposals.append(
            DatasetProposal(
                id=stable_id("example", target_id, content_sha256(task_text)),
                target_id=target_id,
                parent_id=_optional_string(item.get("parent_id"), "parent_id"),
                task_text=task_text,
                assessment=assessment,
                rationales=rationales_from_mapping(rationales_payload),
                source=f"teacher:{invocation.provenance.provider}",
                template_family=_required_string(item.get("template_family"), "template_family"),
                mutation_lineage=target.lineage_id,
                language=_required_string(item.get("language"), "language"),
                mutation_kind=_required_string(item.get("mutation_kind"), "mutation_kind"),
                boundary_dimension=target.boundary_dimension,
                boundary_anchor=target.boundary_anchor,
                provenance=invocation.provenance,
                content_sha256=content_sha256(task_text),
                created_at=utc_now(),
            )
        )
        seen.add(target_id)
    return proposals


def _ratings_from_invocation(
    proposals: list[DatasetProposal],
    invocation: ProviderInvocation,
    rater_id: str,
) -> list[AssessmentRating]:
    items = invocation.payload.get("items")
    if not isinstance(items, list) or len(items) != len(proposals):
        raise ValueError("Provider must return exactly one rating per example.")
    proposal_ids = {proposal.id for proposal in proposals}
    seen: set[str] = set()
    ratings: list[AssessmentRating] = []
    expected_item_keys = {"example_id", "assessment", "rationales"}
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("Rating item must be an object.")
        if set(item) != expected_item_keys:
            raise ValueError(
                f"Rating item fields mismatch: missing={sorted(expected_item_keys - set(item))}, "
                f"additional={sorted(set(item) - expected_item_keys)}."
            )
        example_id = item.get("example_id")
        if not isinstance(example_id, str) or example_id not in proposal_ids or example_id in seen:
            raise ValueError(f"Unknown or duplicate rating example_id {example_id!r}.")
        assessment_payload = item.get("assessment")
        rationales_payload = item.get("rationales")
        if not isinstance(assessment_payload, Mapping) or not isinstance(rationales_payload, Mapping):
            raise ValueError("Rating assessment and rationales must be objects.")
        assessment = TaskAssessment.from_mapping(assessment_payload)
        ratings.append(
            AssessmentRating(
                id=stable_id("rating", example_id, rater_id, invocation.provenance.request_id),
                example_id=example_id,
                rater_id=rater_id,
                assessment=assessment,
                rationales=rationales_from_mapping(rationales_payload),
                provenance=invocation.provenance,
                created_at=utc_now(),
            )
        )
        seen.add(example_id)
    return ratings


def _batch_work(
    targets: list[GenerationTarget],
    provider_names: tuple[str, ...],
    batch_size: int,
) -> list[BatchWork]:
    return [
        BatchWork(index=index, provider_name=provider_names[index % len(provider_names)], targets=tuple(batch))
        for index, batch in enumerate(_chunks(targets, batch_size))
    ]


def _chunks(items: list[Any], size: int) -> Iterable[list[Any]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _append_failure(store: AppendOnlyJsonl, work: BatchWork, error: str, *, retriable: bool) -> None:
    target_ids = [target.id for target in work.targets]
    store.append_unique(
        {
            "id": stable_id("failure", "generate", work.provider_name, *target_ids, error),
            "stage": "generate",
            "provider": work.provider_name,
            "target_ids": target_ids,
            "error": error[:1000],
            "retriable": retriable,
            "created_at": utc_now(),
        }
    )


def _required_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _required_string(value, field_name)
