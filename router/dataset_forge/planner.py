from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from router.core.contracts import Intent, SUB_INTENTS_BY_INTENT
from router.dataset_forge.contracts import RATIONALE_FIELDS, stable_id
from router.orchestration.solvers import SOLVERS


ANCHORS = (0, 2, 5, 8, 10)
LANGUAGES = ("en", "en", "en", "en", "pt-BR", "es")
MUTATIONS = ("canonical", "paraphrase", "typo", "prompt_injection", "strict_format", "long_context")


@dataclass(frozen=True)
class GenerationTarget:
    id: str
    index: int
    intent: Intent
    sub_intent: str
    language: str
    mutation_kind: str
    boundary_dimension: str
    boundary_anchor: int
    lineage_id: str
    parent_target_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.id,
            "intent": self.intent.value,
            "sub_intent": self.sub_intent,
            "language": self.language,
            "mutation_kind": self.mutation_kind,
            "boundary_dimension": self.boundary_dimension,
            "boundary_anchor": self.boundary_anchor,
            "lineage_id": self.lineage_id,
            "parent_target_id": self.parent_target_id,
        }


def build_generation_targets(count: int, *, seed: int = 46) -> list[GenerationTarget]:
    if count < 1:
        raise ValueError("Generation target count must be positive.")
    intents = tuple(Intent)
    solver_sub_intents = {
        intent: tuple(
            sorted(
                {
                    sub_intent
                    for registration in SOLVERS
                    for candidate_intent, sub_intent in registration.capabilities
                    if candidate_intent is intent
                }
            )
        )
        for intent in intents
    }
    targets: list[GenerationTarget] = []
    for index in range(count):
        lineage_index = index // 2
        dimension = RATIONALE_FIELDS[(lineage_index * 3 + seed) % len(RATIONALE_FIELDS)]
        anchor = ANCHORS[(lineage_index + (index % 2) * 2 + seed) % len(ANCHORS)]
        pair_anchors = {
            ANCHORS[(lineage_index + offset * 2 + seed) % len(ANCHORS)]
            for offset in (0, 1)
        }
        intent = intents[(lineage_index + seed) % len(intents)]
        intent_occurrence = lineage_index // len(intents)
        sub_intent_pool = SUB_INTENTS_BY_INTENT[intent]
        if dimension == "deterministic_fit" and pair_anchors & {8, 10} and solver_sub_intents[intent]:
            sub_intent_pool = solver_sub_intents[intent]
        sub_intent = sub_intent_pool[(intent_occurrence + seed) % len(sub_intent_pool)]
        language = LANGUAGES[(lineage_index * 5 + seed) % len(LANGUAGES)]
        mutation = MUTATIONS[(lineage_index * 7 + index % 2 + seed) % len(MUTATIONS)]
        lineage_id = stable_id("lineage", str(seed), str(lineage_index), intent.value, sub_intent)
        target_id = stable_id(
            "target",
            str(seed),
            str(index),
            intent.value,
            sub_intent,
            dimension,
            str(anchor),
            language,
            mutation,
        )
        targets.append(
            GenerationTarget(
                id=target_id,
                index=index,
                intent=intent,
                sub_intent=sub_intent,
                language=language,
                mutation_kind=mutation,
                boundary_dimension=dimension,
                boundary_anchor=anchor,
                lineage_id=lineage_id,
                parent_target_id=targets[-1].id if index % 2 else None,
            )
        )
    return targets


def target_summary(targets: list[GenerationTarget]) -> dict[str, Any]:
    return {
        "count": len(targets),
        "intents": _counts(target.intent.value for target in targets),
        "sub_intents": _counts(target.sub_intent for target in targets),
        "languages": _counts(target.language for target in targets),
        "mutations": _counts(target.mutation_kind for target in targets),
        "boundary_dimensions": _counts(target.boundary_dimension for target in targets),
        "boundary_anchors": _counts(str(target.boundary_anchor) for target in targets),
        "lineages": len({target.lineage_id for target in targets}),
    }


def _counts(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))
