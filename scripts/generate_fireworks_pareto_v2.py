#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = (
    "factual_qa", "math_reasoning", "sentiment", "summarization",
    "ner", "code_debugging", "logic_puzzle", "code_generation",
)


def main() -> int:
    rows = generate()
    output = ROOT / "evals/fireworks-pareto-v2/sealed/tasks.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    manifest = {
        "schema_version": "fireworks-pareto-v2-corpus-v1",
        "rows": len(rows),
        "category_counts": dict(sorted(Counter(row["category"] for row in rows).items())),
        "difficulty_counts": dict(sorted(Counter(row["difficulty"] for row in rows).items())),
        "split_counts": dict(sorted(Counter(row["split"] for row in rows).items())),
        "mechanically_scorable": len(rows),
        "tasks_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "policy": "development selects category policy; sealed rows score frozen policy",
    }
    target = output.parent.parent / "manifest.json"
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0


def generate() -> list[dict]:
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
        for index in range(24):
            difficulty = ("easy", "medium", "hard")[index % 3]
            split = "development" if index < 20 else "sealed"
            prompt, validator, max_tokens, output_shape = factories[category](index, difficulty)
            digest = hashlib.sha256(prompt.encode()).hexdigest()
            rows.append({
                "schema_version": "fireworks-pareto-v2-task-v1",
                "id": f"p2_{category}_{index:02d}",
                "category": category,
                "domain": category,
                "difficulty": difficulty,
                "tier": {"easy": "cheap", "medium": "balanced", "hard": "strong"}[difficulty],
                "split": split,
                "prompt": prompt,
                "prompt_sha256": digest,
                "mutation_lineage": f"p2-{category}-{index // 3:02d}",
                "output_shape": output_shape,
                "max_tokens": max_tokens,
                "validator": validator,
            })
    if len(rows) != len({row["prompt_sha256"] for row in rows}):
        raise AssertionError("duplicate Pareto prompts")
    return rows


def _factual(i, difficulty):
    code = 81000 + i * 37
    distractors = "" if difficulty == "easy" else f" Archive B is {code + 11}. Archive C is {code - 9}."
    prompt = f"Registry P2-{i}: Archive A is {code}.{distractors} Return only Archive A's integer code."
    return prompt, {"type": "exact", "expected": str(code)}, 16, "number"


def _math(i, difficulty):
    a, b, c = 21 + i, 4 + i % 7, 2 + i % 5
    value = a * b - c
    prompt = f"Compute ({a} * {b}) - {c}. Return only the final number."
    if difficulty == "hard":
        prompt = f"A batch has {a} crates with {b} units each; {c} units fail inspection. How many pass? Return only the number."
    return prompt, {"type": "number_exact", "expected": value}, 24, "number"


def _sentiment(i, difficulty):
    label = ("positive", "negative", "neutral")[i % 3]
    phrase = {"positive": "dependable and excellent", "negative": "broken and frustrating", "neutral": "available as specified"}[label]
    prefix = "The packaging was unremarkable. " if difficulty != "easy" else ""
    prompt = f"Review P2-{i}: {prefix}The target component is {phrase}. Return exactly positive, negative, or neutral for the target component."
    return prompt, {"type": "exact_lower", "expected": label}, 12, "label"


def _summary(i, difficulty):
    target = f"The committee approved Project P2-{i} on Friday."
    prompt = f"Notes: Attendance was recorded. {target} Catering was deferred. Return exactly the approval sentence."
    if difficulty == "hard":
        prompt = f"Minutes P2-{i}: Budget discussion continued. Catering was deferred. {target} Return only the sentence that records the decision."
    return prompt, {"type": "exact", "expected": target}, 40, "short_text"


def _ner(i, difficulty):
    person, org, place = f"Mira Vale {i}", f"Helix {i} Labs", f"Nova City {i}"
    prompt = (f"Extract entities from: {person} joined {org} in {place}. Return only minified JSON with "
              'keys person, organization, location.')
    expected = {"person": person, "organization": org, "location": place}
    return prompt, {"type": "json_contains", "expected": expected}, 64, "json"


def _debug(i, difficulty):
    name, offset = f"repair_{i}", 2 + i % 9
    prompt = f"Fix this Python function and return only code:\ndef {name}(value):\n    return value - {offset}"
    cases = [{"args": [1], "expected": 1 + offset}, {"args": [10], "expected": 10 + offset}]
    return prompt, {"type": "python_function_cases", "function_name": name, "cases": cases}, 80, "code"


def _logic(i, difficulty):
    if i % 2 == 0:
        body, expected = f"All rax{i} are tor{i}. Object q{i} is a rax{i}. Is q{i} a tor{i}?", "yes"
    else:
        body, expected = f"All rax{i} are tor{i}. Object q{i} is a tor{i}. Must q{i} be a rax{i}?", "no"
    return body + " Return exactly yes or no.", {"type": "exact_lower", "expected": expected}, 16, "label"


def _codegen(i, difficulty):
    name, offset = f"shift_p2_{i}", 1 + i % 11
    prompt = f"Return only Python code defining {name}(value), which returns value plus {offset}."
    cases = [{"args": [0], "expected": offset}, {"args": [7], "expected": 7 + offset}]
    return prompt, {"type": "python_function_cases", "function_name": name, "cases": cases}, 80, "code"


if __name__ == "__main__":
    raise SystemExit(main())
