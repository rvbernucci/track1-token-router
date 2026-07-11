#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.functiongemma.tooling import DEVELOPER_INSTRUCTION
from router.orchestration.solvers import solve_deterministic


SCHEMA_VERSION = "e2b-mechanical-holdout-v1"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a fresh, mechanically scored E2B selective-routing holdout.")
    parser.add_argument("--per-intent", type=int, default=60)
    parser.add_argument("--seed", type=int, default=4927)
    parser.add_argument("--output", type=Path, default=Path("data/e2b-selective-holdout/tasks.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("data/e2b-selective-holdout/manifest.json"))
    args = parser.parse_args(argv)
    output = _absolute(args.output)
    manifest = _absolute(args.manifest)
    report = generate_holdout(per_intent=args.per_intent, seed=args.seed, output=output, manifest=manifest)
    print(json.dumps(report, sort_keys=True))
    return 0


def generate_holdout(*, per_intent: int, seed: int, output: Path, manifest: Path) -> dict[str, Any]:
    if per_intent < 10:
        raise ValueError("per_intent must be at least 10.")
    rng = random.Random(seed)
    factories = (_sentiment_rows, _ner_rows, _context_qa_rows, _extractive_summary_rows)
    rows: list[dict[str, Any]] = []
    deterministic_rejections = 0
    for factory in factories:
        accepted = 0
        for proposal in factory(rng):
            task = TaskEnvelope(id=proposal["id"], input_text=proposal["input_text"])
            if solve_deterministic(task) is not None:
                deterministic_rejections += 1
                continue
            rows.append(proposal)
            accepted += 1
            if accepted == per_intent:
                break
        if accepted != per_intent:
            raise ValueError(f"{factory.__name__} produced only {accepted} deterministic-refusal rows.")
    rows.sort(key=lambda row: str(row["id"]))
    hashes = [str(row["content_sha256"]) for row in rows]
    if len(hashes) != len(set(hashes)):
        raise AssertionError("Generated holdout contains duplicate prompts.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "seed": seed,
        "rows": len(rows),
        "per_intent": per_intent,
        "intent_counts": dict(sorted(Counter(str(row["source_assessment"]["intent"]) for row in rows).items())),
        "evaluator_counts": dict(sorted(Counter(str(row["evaluation"]["type"]) for row in rows).items())),
        "deterministic_acceptances_excluded": deterministic_rejections,
        "all_runtime_solver_refusals": all(
            solve_deterministic(TaskEnvelope(id=str(row["id"]), input_text=str(row["input_text"]))) is None
            for row in rows
        ),
        "output_sha256": _sha256(output),
        "generation_policy": "template_combinatorics_with_gold_known_before_model_inference",
        "promotion_use": "fresh_holdout_only; never fit thresholds or coefficients on these rows",
    }
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _sentiment_rows(rng: random.Random) -> Iterable[dict[str, Any]]:
    aspects = ("battery life", "customer support", "screen quality", "delivery service", "setup process")
    positive = ("excellent", "reliable", "impressive", "smooth", "delightful", "outstanding")
    negative = ("awful", "unreliable", "frustrating", "poor", "disappointing", "terrible")
    neutral = ("adequate", "ordinary", "average", "unremarkable", "acceptable", "standard")
    labels = (("positive", positive), ("negative", negative), ("neutral", neutral))
    distractors = (("camera", positive), ("packaging", negative), ("price", neutral))
    combinations = [
        (aspect, label, adjective, distractor, rng.choice(distractor_words))
        for aspect in aspects
        for label, adjectives in labels
        for adjective in adjectives
        for distractor, distractor_words in distractors
    ]
    rng.shuffle(combinations)
    for index, (aspect, label, adjective, distractor, distractor_adjective) in enumerate(combinations):
        prompt = (
            f'Review: "The {distractor} is {distractor_adjective}, while the {aspect} is {adjective}."\n\n'
            f"Classify sentiment toward {aspect} only. Answer exactly one label: positive, negative, or neutral."
        )
        yield _row(
            family="aspect_sentiment_gold",
            index=index,
            prompt=prompt,
            assessment=_assessment("sentiment", 1, 2, 0, 0, 2),
            expected=label,
            evaluator="label",
        )


def _ner_rows(rng: random.Random) -> Iterable[dict[str, Any]]:
    people = ("Ava Stone", "Noah Reed", "Maya Chen", "Leo Martins", "Sofia Costa", "Eli Brooks", "Nina Patel", "Owen Silva")
    organizations = ("Orion Labs", "Cedar Works", "Atlas Systems", "Nova Health", "Harbor Analytics", "Lumen Robotics")
    locations = ("Lisbon", "Recife", "Toronto", "Madrid", "Nairobi", "Oslo", "Santiago")
    combinations = [(person, org, location) for person in people for org in organizations for location in locations]
    rng.shuffle(combinations)
    for index, (person, organization, location) in enumerate(combinations):
        prompt = (
            f"Memo: {person} joined {organization} during its expansion into {location}. "
            "The announcement was approved yesterday.\n\n"
            'Extract the named entities. Return only valid JSON with exactly these keys: '
            '"person", "organization", "location".'
        )
        yield _row(
            family="source_bound_ner_gold",
            index=index,
            prompt=prompt,
            assessment=_assessment("ner", 2, 2, 0, 2, 7),
            expected={"person": person, "organization": organization, "location": location},
            evaluator="json_object",
        )


def _context_qa_rows(rng: random.Random) -> Iterable[dict[str, Any]]:
    projects = ("Atlas", "Boreal", "Cobalt", "Drift", "Ember", "Fjord", "Grove", "Helix")
    owners = ("Mara", "Tomas", "Iris", "Kenji", "Lina", "Pavel", "Ravi", "Zoe")
    cities = ("Porto", "Salvador", "Prague", "Kyoto", "Lima", "Tallinn", "Quito", "Dublin")
    combinations = [(project, owner, city, 3100 + index * 37) for index, (project, owner, city) in enumerate(zip(projects * 8, owners * 8, cities * 8))]
    rng.shuffle(combinations)
    for index, (project, owner, city, code) in enumerate(combinations):
        other = projects[(projects.index(project) + 3) % len(projects)]
        prompt = (
            f"Internal context: Project {project} is owned by {owner}, operates from {city}, and uses access code {code}. "
            f"Project {other} is a separate initiative with code {code + 11}.\n\n"
            f"According only to the context, what is the access code for Project {project}? Return only the code."
        )
        yield _row(
            family="context_qa_gold",
            index=index,
            prompt=prompt,
            assessment=_assessment("factual_qa", 2, 2, 0, 0, 2),
            expected=str(code),
            evaluator="exact",
        )


def _extractive_summary_rows(rng: random.Random) -> Iterable[dict[str, Any]]:
    projects = ("Atlas", "Boreal", "Cobalt", "Drift", "Ember", "Fjord", "Grove", "Helix")
    amounts = ("$2 million", "$3.5 million", "$5 million", "$7 million", "$8.5 million", "$10 million")
    verbs = ("approved", "authorized", "confirmed", "ratified")
    combinations = [(project, amount, verb) for project in projects for amount in amounts for verb in verbs]
    rng.shuffle(combinations)
    for index, (project, amount, verb) in enumerate(combinations):
        decision = f"The board {verb} {amount} for Project {project}."
        prompt = (
            "Meeting notes: The finance team reviewed quarterly forecasts. "
            f"{decision} "
            "Recruitment plans will be discussed next month. The meeting ended at 4 PM.\n\n"
            "Return exactly the single sentence containing the approved funding decision, with no commentary."
        )
        yield _row(
            family="extractive_summary_gold",
            index=index,
            prompt=prompt,
            assessment=_assessment("summarization", 2, 2, 0, 2, 4),
            expected=decision,
            evaluator="exact",
        )


def _row(
    *,
    family: str,
    index: int,
    prompt: str,
    assessment: Mapping[str, Any],
    expected: Any,
    evaluator: str,
) -> dict[str, Any]:
    digest = hashlib.sha256(f"{SCHEMA_VERSION}\0{family}\0{index}\0{prompt}".encode()).hexdigest()
    task_id = f"mechanical_{digest[:20]}"
    return {
        "schema_version": SCHEMA_VERSION,
        "id": task_id,
        "input_text": prompt,
        "content_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "template_family": family,
        "mutation_lineage": f"fresh_{digest[20:40]}",
        "mutation_kind": "fresh_mechanical",
        "regression_split": "fresh_holdout",
        "source": "mechanical_generator",
        "source_assessment": assessment,
        "evaluation": {"type": evaluator, "expected": expected},
        "messages": [
            {"role": "developer", "content": DEVELOPER_INSTRUCTION},
            {"role": "user", "content": prompt},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {"name": "assess_task", "arguments": assessment},
                    }
                ],
            },
        ],
    }


def _assessment(
    intent: str,
    deterministic_fit: int,
    reasoning_demand: int,
    knowledge_uncertainty: int,
    generation_demand: int,
    format_complexity: int,
) -> dict[str, Any]:
    return {
        "intent": intent,
        "scores": {
            "deterministic_fit": deterministic_fit,
            "reasoning_demand": reasoning_demand,
            "knowledge_uncertainty": knowledge_uncertainty,
            "generation_demand": generation_demand,
            "format_complexity": format_complexity,
        },
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
