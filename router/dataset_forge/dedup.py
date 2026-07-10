from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from router.dataset_forge.contracts import DatasetProposal


@dataclass(frozen=True)
class DedupDecision:
    example_id: str
    accepted: bool
    duplicate_of: str | None
    reason: str
    similarity: float

    def to_dict(self) -> dict[str, object]:
        return {
            "id": f"dedup_{self.example_id}",
            "example_id": self.example_id,
            "accepted": self.accepted,
            "duplicate_of": self.duplicate_of,
            "reason": self.reason,
            "similarity": self.similarity,
        }


def deduplicate(proposals: list[DatasetProposal]) -> tuple[list[DatasetProposal], list[DedupDecision]]:
    accepted: list[DatasetProposal] = []
    decisions: list[DedupDecision] = []
    exact_by_hash: dict[str, DatasetProposal] = {}
    accepted_by_target: dict[str, DatasetProposal] = {}
    for proposal in sorted(proposals, key=lambda item: item.id):
        target_match = accepted_by_target.get(proposal.target_id)
        if target_match is not None:
            decisions.append(DedupDecision(proposal.id, False, target_match.id, "target_id_collision", 1.0))
            continue
        exact = exact_by_hash.get(proposal.content_sha256)
        if exact is not None:
            decisions.append(DedupDecision(proposal.id, False, exact.id, "exact_normalized_duplicate", 1.0))
            continue
        duplicate, similarity, reason = _nearest_duplicate(proposal, accepted)
        if duplicate is not None:
            decisions.append(DedupDecision(proposal.id, False, duplicate.id, reason, similarity))
            continue
        accepted.append(proposal)
        accepted_by_target[proposal.target_id] = proposal
        exact_by_hash[proposal.content_sha256] = proposal
        decisions.append(DedupDecision(proposal.id, True, None, "unique", 0.0))
    return accepted, decisions


def _nearest_duplicate(
    candidate: DatasetProposal,
    accepted: list[DatasetProposal],
) -> tuple[DatasetProposal | None, float, str]:
    candidate_tokens = _token_shingles(candidate.task_text)
    candidate_simhash = _simhash(candidate.task_text)
    for existing in accepted:
        if _is_boundary_pair(candidate, existing):
            continue
        length_ratio = min(len(candidate.task_text), len(existing.task_text)) / max(
            1, max(len(candidate.task_text), len(existing.task_text))
        )
        if length_ratio < 0.75:
            continue
        similarity = _jaccard(candidate_tokens, _token_shingles(existing.task_text))
        if similarity >= 0.90:
            return existing, similarity, "token_shingle_near_duplicate"
        distance = (candidate_simhash ^ _simhash(existing.task_text)).bit_count()
        if distance <= 3:
            return existing, 1.0 - distance / 64.0, "simhash_near_duplicate"
    return None, 0.0, ""


def _is_boundary_pair(left: DatasetProposal, right: DatasetProposal) -> bool:
    return (
        left.mutation_lineage == right.mutation_lineage
        and left.boundary_dimension == right.boundary_dimension
        and left.boundary_anchor != right.boundary_anchor
    )


def _token_shingles(text: str) -> set[tuple[str, ...]]:
    tokens = re.findall(r"\w+|[^\w\s]", text.casefold(), flags=re.UNICODE)
    if len(tokens) < 3:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[index : index + 3]) for index in range(len(tokens) - 2)}


def _jaccard(left: set[tuple[str, ...]], right: set[tuple[str, ...]]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _simhash(text: str) -> int:
    tokens = re.findall(r"\w+", text.casefold(), flags=re.UNICODE)
    weights = [0] * 64
    for token in tokens:
        digest = int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "big")
        for bit in range(64):
            weights[bit] += 1 if digest & (1 << bit) else -1
    fingerprint = 0
    for bit, weight in enumerate(weights):
        if weight >= 0:
            fingerprint |= 1 << bit
    return fingerprint
