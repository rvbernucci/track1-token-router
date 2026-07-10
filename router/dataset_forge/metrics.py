from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from statistics import mean
from typing import Any

from router.dataset_forge.contracts import AssessmentRating, DatasetProposal, GoldAssessment, RATIONALE_FIELDS
from router.dataset_forge.pipeline import ForgePaths
from router.dataset_forge.storage import AppendOnlyJsonl


def build_report(paths: ForgePaths) -> dict[str, Any]:
    proposals = [
        DatasetProposal.from_mapping(payload)
        for payload in AppendOnlyJsonl(paths.raw_proposals).read_all()
    ]
    validated = AppendOnlyJsonl(paths.validated_proposals).read_all()
    deduped = AppendOnlyJsonl(paths.deduped_proposals).read_all()
    ratings = [
        AssessmentRating.from_mapping(payload)
        for payload in AppendOnlyJsonl(paths.ratings).read_all()
    ]
    gold_path = paths.root / "adjudicated" / "gold.jsonl"
    gold_history = [GoldAssessment.from_mapping(payload) for payload in AppendOnlyJsonl(gold_path).read_all()]
    gold = list(_latest_gold(gold_history).values())
    failures = AppendOnlyJsonl(paths.failures).read_all()
    agreement = agreement_metrics(ratings)
    provenance_by_request = {
        item.provenance.request_id: item.provenance
        for item in [*proposals, *ratings]
    }
    billable = sum(item.billable_cost_usd for item in provenance_by_request.values())
    accepted_gold = sum(item.adjudication_status == "accepted" for item in gold)
    return {
        "generated": len(proposals),
        "validated": len(validated),
        "deduplicated": len(deduped),
        "duplicate_rate": 1 - len(deduped) / len(validated) if validated else 0.0,
        "ratings": len(ratings),
        "rater_families": sorted({f"{item.provenance.provider}:{item.provenance.model}" for item in ratings}),
        "gold_total": len(gold),
        "gold_revisions": len(gold_history),
        "gold_accepted": accepted_gold,
        "gold_needs_review": sum(item.adjudication_status == "needs_review" for item in gold),
        "failures": len(failures),
        "fireworks_billable_usd": round(billable, 10),
        "fireworks_usd_per_accepted_gold": round(billable / accepted_gold, 10) if accepted_gold else None,
        "agreement": agreement,
    }


def agreement_metrics(ratings: list[AssessmentRating]) -> dict[str, Any]:
    grouped: dict[str, list[AssessmentRating]] = defaultdict(list)
    for rating in ratings:
        grouped[rating.example_id].append(rating)
    pairs = [
        pair
        for example_ratings in grouped.values()
        for pair in combinations(_one_per_family(example_ratings), 2)
    ]
    if not pairs:
        return {
            "pair_count": 0,
            "intent_exact": None,
            "sub_intent_exact": None,
            "score_mae": {name: None for name in RATIONALE_FIELDS},
            "weighted_quadratic_kappa": {name: None for name in RATIONALE_FIELDS},
        }
    intent_exact = mean(float(left.assessment.intent is right.assessment.intent) for left, right in pairs)
    sub_exact = mean(
        float(
            left.assessment.intent is right.assessment.intent
            and left.assessment.sub_intent == right.assessment.sub_intent
        )
        for left, right in pairs
    )
    score_pairs = {
        name: [
            (getattr(left.assessment.scores, name), getattr(right.assessment.scores, name))
            for left, right in pairs
        ]
        for name in RATIONALE_FIELDS
    }
    return {
        "pair_count": len(pairs),
        "intent_exact": intent_exact,
        "sub_intent_exact": sub_exact,
        "score_mae": {
            name: mean(abs(left - right) for left, right in values)
            for name, values in score_pairs.items()
        },
        "weighted_quadratic_kappa": {
            name: weighted_quadratic_kappa(values)
            for name, values in score_pairs.items()
        },
    }


def weighted_quadratic_kappa(pairs: list[tuple[int, int]], *, categories: int = 11) -> float | None:
    if not pairs:
        return None
    observed = [[0.0 for _ in range(categories)] for _ in range(categories)]
    left_counts = [0.0] * categories
    right_counts = [0.0] * categories
    for left, right in pairs:
        observed[left][right] += 1
        left_counts[left] += 1
        right_counts[right] += 1
    total = float(len(pairs))
    weighted_observed = 0.0
    weighted_expected = 0.0
    denominator = float((categories - 1) ** 2)
    for left in range(categories):
        for right in range(categories):
            weight = ((left - right) ** 2) / denominator
            weighted_observed += weight * observed[left][right] / total
            weighted_expected += weight * (left_counts[left] * right_counts[right]) / (total * total)
    if weighted_expected == 0:
        return 1.0 if weighted_observed == 0 else 0.0
    return 1.0 - weighted_observed / weighted_expected


def _one_per_family(ratings: list[AssessmentRating]) -> list[AssessmentRating]:
    selected: dict[tuple[str, str], AssessmentRating] = {}
    for rating in sorted(ratings, key=lambda item: item.id):
        selected.setdefault((rating.provenance.provider, rating.provenance.model), rating)
    return list(selected.values())


def _latest_gold(items: list[GoldAssessment]) -> dict[str, GoldAssessment]:
    latest: dict[str, GoldAssessment] = {}
    for item in items:
        current = latest.get(item.example_id)
        if current is None or item.revision > current.revision:
            latest[item.example_id] = item
    return latest
