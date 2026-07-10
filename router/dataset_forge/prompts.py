from __future__ import annotations

import json
from typing import Any

from router.core.contracts import Intent, SUB_INTENTS_BY_INTENT
from router.dataset_forge.planner import GenerationTarget
from router.orchestration.solvers import solver_manifest


RUBRIC_COMPACT = """Score each dimension with an anchored integer 0..10.
deterministic_fit: 0 no mechanical contract; 2 superficial pattern; 5 partial structure; 8 registered solver likely; 10 exact provable transformation.
reasoning_demand: 0 lookup/label; 2 one step; 5 dependent steps; 8 difficult planning/deduction/debugging; 10 deep fragile specialized reasoning.
knowledge_uncertainty: 0 prompt-contained/stable; 2 stable general knowledge; 5 domain uncertainty; 8 current/external/source-dependent; 10 unverifiable from context.
generation_demand: 0 label/token; 2 short fact; 5 paragraph/small code; 8 substantial text/code; 10 long multi-part generation.
format_complexity: 0 free text; 2 simple short answer; 5 multiple constraints; 8 strict schema/exact match; 10 fragile nested/multi-artifact.
Intermediate integers interpolate between adjacent anchors."""


SOLVER_EVIDENCE = """deterministic_fit is grounded in the actual local registry below, not generic solvability.
Score 10 only for an exact full-match contract whose answer is mechanically provable from the untouched task.
Score 8 when a listed contract is very likely to accept but the surface form has limited ambiguity.
Score 5 when only part is mechanical or semantic judgment remains.
Score 2 for a superficial resemblance that the strict solver should refuse, and 0 when no listed capability applies.
The registered solver still rechecks the original task; a model label never grants execution."""


def generation_prompt(targets: list[GenerationTarget]) -> str:
    target_payload = [target.to_dict() for target in targets]
    return f"""Create exactly {len(targets)} diverse unseen Track 1 task examples, one per target below.

Do not solve or answer any task. The task_text is what a future answer model would receive.
Copy each target_id exactly. Keep the requested intent and sub_intent exactly.
Set boundary_dimension to the target value and make that score land exactly on boundary_anchor while scoring all dimensions honestly.
Use short evidence statements in rationales, not hidden chain-of-thought.
Never include engine, route, model, confidence, or answer fields.
template_family must describe the reusable structural family without embedding the answer.
mutation_lineage must copy lineage_id. parent_id must copy parent_target_id exactly, including null.

Allowed taxonomy:
{json.dumps({intent.value: list(SUB_INTENTS_BY_INTENT[intent]) for intent in Intent}, ensure_ascii=False, sort_keys=True)}

Rubric:
{RUBRIC_COMPACT}

Deterministic solver evidence:
{SOLVER_EVIDENCE}
Registry manifest:
{json.dumps(solver_manifest(), ensure_ascii=False, sort_keys=True)}

Targets:
{json.dumps(target_payload, ensure_ascii=False, sort_keys=True)}
"""


def rating_prompt(items: list[dict[str, Any]], *, rater_id: str) -> str:
    visible = [{"example_id": item["id"], "task_text": item["task_text"]} for item in items]
    return f"""Independently assess exactly {len(items)} Track 1 tasks as rater {rater_id}.

Do not answer the tasks. Do not infer or copy another model's labels; only task_text is supplied.
Return each example_id exactly once. Choose one allowed intent/sub_intent pair and five integer scores.
Use short evidence statements in rationales, not hidden chain-of-thought.
Never emit engine, route, model, confidence, or answer fields.

Allowed taxonomy:
{json.dumps({intent.value: list(SUB_INTENTS_BY_INTENT[intent]) for intent in Intent}, ensure_ascii=False, sort_keys=True)}

Rubric:
{RUBRIC_COMPACT}

Deterministic solver evidence:
{SOLVER_EVIDENCE}
Registry manifest:
{json.dumps(solver_manifest(), ensure_ascii=False, sort_keys=True)}

Tasks:
{json.dumps(visible, ensure_ascii=False, sort_keys=True)}
"""
