#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = (
    "factual_qa", "math_reasoning", "sentiment", "summarization",
    "ner", "code_debugging", "logic_puzzle", "code_generation",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the fresh Sprint 65 mechanical boundary corpus.")
    parser.add_argument("--per-category", type=int, default=60)
    parser.add_argument("--seed", type=int, default=65065)
    parser.add_argument("--output", type=Path, default=Path("evals/e2b-boundary-v1/sealed/tasks.jsonl"))
    parser.add_argument("--manifest", type=Path, default=Path("evals/e2b-boundary-v1/manifest.json"))
    args = parser.parse_args()
    rows = generate(args.per_category, args.seed)
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    for split in ("train", "calibration"):
        path = output.parent.parent / split / "tasks.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    manifest = {
        "schema_version": "e2b-boundary-corpus-v1",
        "seed": args.seed,
        "rows": len(rows),
        "per_category": args.per_category,
        "category_counts": dict(sorted(Counter(row["category"] for row in rows).items())),
        "split_counts": {"train": 0, "calibration": 0, "sealed": len(rows)},
        "policy": "sealed audit only; no fitting or threshold selection",
        "tasks_sha256": _sha256(output),
        "unique_prompt_hashes": len({row["prompt_sha256"] for row in rows}) == len(rows),
        "generator": "template combinatorics with gold fixed before inference",
    }
    target = ROOT / args.manifest
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0


def generate(per_category: int, seed: int) -> list[dict]:
    if per_category < 60:
        raise ValueError("per_category must be at least 60")
    rng = random.Random(seed)
    factories = {
        "factual_qa": _factual,
        "math_reasoning": _math,
        "sentiment": _sentiment,
        "summarization": _summary,
        "ner": _ner,
        "code_debugging": _debug,
        "logic_puzzle": _logic,
        "code_generation": _codegen,
    }
    rows = []
    for category in CATEGORIES:
        candidates = factories[category](per_category * 2)
        rng.shuffle(candidates)
        rows.extend(candidates[:per_category])
    rows.sort(key=lambda row: row["task_id"])
    if len(rows) != len({row["prompt_sha256"] for row in rows}):
        raise AssertionError("boundary corpus contains duplicate prompts")
    return rows


def _row(category: str, index: int, prompt: str, evaluator: str, expected, *, language="en", shape="short_text"):
    lineage = hashlib.sha256(f"s65:{category}:{index}".encode()).hexdigest()[:20]
    digest = hashlib.sha256(prompt.encode()).hexdigest()
    return {
        "schema_version": "e2b-boundary-task-v1", "task_id": f"s65_{category}_{lineage}",
        "prompt": prompt, "prompt_sha256": digest, "mutation_lineage": f"boundary_{lineage}",
        "category": category, "language": language, "output_shape": shape,
        "evaluation": {"type": evaluator, "expected": expected},
    }


def _factual(count):
    rows=[]
    for i in range(count):
        project=f"Project Q{3100+i}"; code=73000+i*17
        prompt=(f"Record B65-{i}: {project} uses access code {code}; Project R{4100+i} uses {code+9}. "
                f"According only to this record, return only the access code for {project}.")
        rows.append(_row("factual_qa",i,prompt,"exact",str(code),shape="number"))
    return rows


def _math(count):
    rows=[]
    for i in range(count):
        a=37+i; b=11+(i%13); c=3+(i%7); expected=a*b-c
        prompt=f"Boundary calculation M65-{i}: compute {a} * {b} - {c}. Return only the final integer."
        rows.append(_row("math_reasoning",i,prompt,"number",expected,shape="number"))
    return rows


def _sentiment(count):
    labels=("positive","negative","neutral")
    words={"positive":"excellent and reliable","negative":"awful and unreliable","neutral":"ordinary and adequate"}
    rows=[]
    for i in range(count):
        label=labels[i%3]; target=f"module-{i}"
        prompt=(f"Ticket S65-{i}: The packaging was ordinary, but the {target} was {words[label]}. "
                f"Classify sentiment toward {target} only. Return exactly positive, negative, or neutral.")
        rows.append(_row("sentiment",i,prompt,"label",label))
    return rows


def _summary(count):
    rows=[]
    verbs=("approved","authorized","confirmed")
    for i in range(count):
        sentence=f"The board {verbs[i%3]} ${2+i} million for Initiative Z65-{i}."
        prompt=(f"Notes U65-{i}: Forecasts were reviewed. {sentence} Hiring will be discussed later. "
                "Return exactly the single sentence containing the funding decision, with no commentary.")
        rows.append(_row("summarization",i,prompt,"exact",sentence,shape="free_text"))
    return rows


def _ner(count):
    rows=[]
    for i in range(count):
        person=f"Ava Stone-{i}"; org=f"Orion-{i} Labs"; city=f"Porto-{i}"
        prompt=(f"Memo N65-{i}: {person} joined {org} during expansion into {city}. Return only minified JSON "
                'with exactly the keys "person", "organization", and "location".')
        rows.append(_row("ner",i,prompt,"json",{"person":person,"organization":org,"location":city},shape="json"))
    return rows


def _debug(count):
    rows=[]
    for i in range(count):
        offset=2+(i%9); expected=f"def add_offset_{i}(value):\n    return value + {offset}"
        prompt=(f"Fix this Python function. Return only corrected Python code.\n\n"
                f"def add_offset_{i}(value):\n    return value - {offset}")
        rows.append(_row("code_debugging",i,prompt,"exact_code",expected,shape="code"))
    return rows


def _logic(count):
    rows=[]
    for i in range(count):
        yes=i%2==0
        if yes:
            body=f"All dax{i} are lim{i}. Object x{i} is a dax{i}. Is x{i} a lim{i}?"
        else:
            body=f"All dax{i} are lim{i}. Object x{i} is a lim{i}. Is x{i} guaranteed to be a dax{i}?"
        prompt=f"Logic L65-{i}: {body} Return exactly yes or no."
        rows.append(_row("logic_puzzle",i,prompt,"label","yes" if yes else "no"))
    return rows


def _codegen(count):
    rows=[]
    for i in range(count):
        offset=1+(i%11); expected=f"def shift_{i}(value):\n    return value + {offset}"
        prompt=f"Return only Python code. Define shift_{i}(value) that returns value plus {offset}."
        rows.append(_row("code_generation",i,prompt,"exact_code",expected,shape="code"))
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
