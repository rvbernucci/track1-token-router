from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from statistics import median
from typing import Any

from router.core.contracts import AssessmentScores, Intent, TaskAssessment
from router.dataset_forge.contracts import (
    AssessmentRating,
    DatasetProposal,
    GoldAssessment,
    stable_id,
    utc_now,
)
from router.dataset_forge.pipeline import ForgePaths
from router.dataset_forge.storage import AppendOnlyJsonl


ADJUDICATION_POLICY_VERSION = "assessment-adjudication-v3"


def adjudicate(paths: ForgePaths) -> dict[str, int]:
    proposals = {
        proposal.id: proposal
        for proposal in (
            DatasetProposal.from_mapping(payload)
            for payload in AppendOnlyJsonl(paths.deduped_proposals).read_all()
        )
    }
    grouped: dict[str, list[AssessmentRating]] = defaultdict(list)
    for payload in AppendOnlyJsonl(paths.ratings).read_all():
        rating = AssessmentRating.from_mapping(payload)
        grouped[rating.example_id].append(rating)

    gold_store = AppendOnlyJsonl(paths.root / "adjudicated" / "gold.jsonl")
    existing_gold = [GoldAssessment.from_mapping(payload) for payload in gold_store.read_all()]
    latest_gold = _latest_gold(existing_gold)
    manual_reviews = _latest_manual_reviews(AppendOnlyJsonl(paths.manual_reviews).read_all())
    counts = {"accepted": 0, "needs_review": 0, "rejected": 0, "insufficient_ratings": 0, "written": 0}
    for example_id, proposal in sorted(proposals.items()):
        ratings = grouped.get(example_id, [])
        independent = _independent_ratings(ratings)
        if len(independent) < 2:
            counts["insufficient_ratings"] += 1
            continue
        previous = latest_gold.get(example_id)
        rating_ids = tuple(rating.id for rating in independent)
        manual_review = manual_reviews.get(example_id)
        review_id = str(manual_review["id"]) if manual_review else ""
        expected_gold_id = stable_id(
            "gold",
            ADJUDICATION_POLICY_VERSION,
            proposal.id,
            *rating_ids,
            review_id,
        )
        if previous is not None and previous.id == expected_gold_id:
            counts[previous.adjudication_status] += 1
            continue
        gold = _adjudicate_one(
            proposal,
            independent,
            previous=previous,
            manual_review=manual_review,
        )
        counts[gold.adjudication_status] += 1
        if gold_store.append_unique(gold.to_dict()):
            counts["written"] += 1
    return counts


def _independent_ratings(ratings: list[AssessmentRating]) -> list[AssessmentRating]:
    selected: list[AssessmentRating] = []
    seen_families: set[tuple[str, str]] = set()
    for rating in sorted(ratings, key=lambda item: (item.provenance.provider, item.provenance.model, item.id)):
        family = (rating.provenance.provider, rating.provenance.model)
        if family in seen_families:
            continue
        seen_families.add(family)
        selected.append(rating)
    return selected


def _adjudicate_one(
    proposal: DatasetProposal,
    ratings: list[AssessmentRating],
    *,
    previous: GoldAssessment | None,
    manual_review: dict[str, Any] | None,
) -> GoldAssessment:
    contract_ratings = [
        rating
        for rating in ratings
        if rating.provenance.provider == "mechanical" and rating.provenance.model == "target-contract-v1"
    ]
    semantic_ratings = [rating for rating in ratings if rating not in contract_ratings]
    if len(contract_ratings) == 1 and semantic_ratings:
        return _adjudicate_contract_and_semantics(
            proposal,
            contract_ratings[0],
            semantic_ratings,
            previous=previous,
            manual_review=manual_review,
        )

    intent_values = [rating.assessment.intent for rating in ratings]
    intent, intent_count = _majority(intent_values)
    sub_values = [
        rating.assessment.sub_intent
        for rating in ratings
        if rating.assessment.intent is intent
    ]
    sub_intent, sub_count = _majority(sub_values) if sub_values else (proposal.assessment.sub_intent, 0)
    intent_agreement = intent_count / len(ratings)
    sub_agreement = sub_count / len(ratings)
    score_values = {
        name: [getattr(rating.assessment.scores, name) for rating in ratings]
        for name in proposal.assessment.scores.to_dict()
    }
    max_spread = max(max(values) - min(values) for values in score_values.values())
    median_scores = {name: _round_half_up(median(values)) for name, values in score_values.items()}
    scores = AssessmentScores(**median_scores)
    try:
        assessment = TaskAssessment(intent=intent, sub_intent=sub_intent, scores=scores)
    except ValueError:
        assessment = proposal.assessment
        sub_agreement = 0.0

    required_majority = math.floor(len(ratings) / 2) + 1
    if len(ratings) == 2:
        score_consensus = max_spread <= 2
    else:
        score_consensus = all(
            sum(abs(value - median_scores[name]) <= 2 for value in values) >= required_majority
            for name, values in score_values.items()
        )
    accepted = (
        intent_count >= required_majority
        and sub_count >= required_majority
        and score_consensus
    )
    status = "accepted" if accepted else "needs_review"
    adjudicator = "independent-majority-median-v1"
    review_id = ""
    if manual_review is not None:
        assessment = TaskAssessment.from_mapping(manual_review["assessment"])
        status = "accepted"
        adjudicator = str(manual_review["adjudicator"])
        review_id = str(manual_review["id"])
    return GoldAssessment(
        id=stable_id(
            "gold",
            ADJUDICATION_POLICY_VERSION,
            proposal.id,
            *(rating.id for rating in ratings),
            review_id,
        ),
        example_id=proposal.id,
        assessment=assessment,
        rating_ids=tuple(rating.id for rating in ratings),
        adjudication_status=status,
        intent_agreement=min(intent_agreement, sub_agreement),
        max_score_spread=max_spread,
        adjudicator=adjudicator,
        created_at=utc_now(),
        revision=(previous.revision + 1) if previous else 1,
        supersedes_id=previous.id if previous else None,
    )


def _adjudicate_contract_and_semantics(
    proposal: DatasetProposal,
    contract: AssessmentRating,
    semantic_ratings: list[AssessmentRating],
    *,
    previous: GoldAssessment | None,
    manual_review: dict[str, Any] | None,
) -> GoldAssessment:
    matching = [
        rating
        for rating in semantic_ratings
        if rating.assessment.intent is contract.assessment.intent
        and rating.assessment.sub_intent == contract.assessment.sub_intent
    ]
    required_majority = math.floor(len(semantic_ratings) / 2) + 1
    taxonomy_consensus = len(matching) >= required_majority
    score_sources = matching or semantic_ratings
    semantic_scores = {
        name: [getattr(rating.assessment.scores, name) for rating in score_sources]
        for name in proposal.assessment.scores.to_dict()
    }
    median_scores = {name: _round_half_up(median(values)) for name, values in semantic_scores.items()}
    if proposal.boundary_dimension is not None and proposal.boundary_anchor is not None:
        median_scores[proposal.boundary_dimension] = proposal.boundary_anchor
    scores = AssessmentScores(**median_scores)
    assessment = TaskAssessment(
        intent=contract.assessment.intent,
        sub_intent=contract.assessment.sub_intent,
        scores=scores,
    )
    semantic_spreads = {
        name: max(values) - min(values)
        for name, values in semantic_scores.items()
        if name != proposal.boundary_dimension
    }
    max_spread = max(semantic_spreads.values(), default=0)
    score_consensus = max_spread <= 2
    status = "accepted" if taxonomy_consensus and score_consensus else "needs_review"
    adjudicator = "target-contract-plus-semantic-median-v1"
    review_id = ""
    if manual_review is not None:
        assessment = TaskAssessment.from_mapping(manual_review["assessment"])
        status = "accepted"
        adjudicator = str(manual_review["adjudicator"])
        review_id = str(manual_review["id"])
    ordered_ratings = [contract, *semantic_ratings]
    return GoldAssessment(
        id=stable_id(
            "gold",
            ADJUDICATION_POLICY_VERSION,
            proposal.id,
            *(rating.id for rating in ordered_ratings),
            review_id,
        ),
        example_id=proposal.id,
        assessment=assessment,
        rating_ids=tuple(rating.id for rating in ordered_ratings),
        adjudication_status=status,
        intent_agreement=len(matching) / len(semantic_ratings),
        max_score_spread=max_spread,
        adjudicator=adjudicator,
        created_at=utc_now(),
        revision=(previous.revision + 1) if previous else 1,
        supersedes_id=previous.id if previous else None,
    )


def _majority(values: list[Any]) -> tuple[Any, int]:
    if not values:
        raise ValueError("Cannot choose majority from an empty sequence.")
    counts = Counter(values)
    winner, count = sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))[0]
    return winner, count


def _round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def _latest_gold(items: list[GoldAssessment]) -> dict[str, GoldAssessment]:
    latest: dict[str, GoldAssessment] = {}
    for item in items:
        current = latest.get(item.example_id)
        if current is None or item.revision > current.revision:
            latest[item.example_id] = item
    return latest


def apply_manual_reviews(paths: ForgePaths, review_path) -> dict[str, int]:
    proposals = {
        payload["id"]
        for payload in AppendOnlyJsonl(paths.deduped_proposals).read_all()
        if isinstance(payload.get("id"), str)
    }
    store = AppendOnlyJsonl(paths.manual_reviews)
    written = 0
    for line_no, line in enumerate(review_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"Manual review line {line_no} must be an object.")
        expected = {"example_id", "assessment", "evidence", "adjudicator"}
        if set(payload) != expected:
            raise ValueError(f"Manual review line {line_no} fields must be exactly {sorted(expected)}.")
        example_id = payload["example_id"]
        evidence = payload["evidence"]
        adjudicator = payload["adjudicator"]
        if example_id not in proposals:
            raise ValueError(f"Manual review references unknown example {example_id!r}.")
        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError("Manual review evidence is required.")
        if not isinstance(adjudicator, str) or not adjudicator.strip():
            raise ValueError("Manual review adjudicator is required.")
        assessment = TaskAssessment.from_mapping(payload["assessment"])
        record = {
            "id": stable_id("review", example_id, assessment.to_json(), evidence, adjudicator),
            "schema_version": "manual-assessment-review-v1",
            "example_id": example_id,
            "assessment": assessment.to_dict(),
            "evidence": evidence.strip(),
            "adjudicator": adjudicator.strip(),
            "created_at": utc_now(),
        }
        if store.append_unique(record):
            written += 1
    return {"written": written}


def _latest_manual_reviews(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        expected = {"id", "schema_version", "example_id", "assessment", "evidence", "adjudicator", "created_at"}
        if set(record) != expected or record.get("schema_version") != "manual-assessment-review-v1":
            raise ValueError("Invalid manual assessment review record.")
        TaskAssessment.from_mapping(record["assessment"])
        latest[str(record["example_id"])] = record
    return latest
