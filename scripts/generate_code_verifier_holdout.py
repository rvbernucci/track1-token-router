#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]


PROMPTS = {
    "add": "Write only a Python function named add(a, b) that returns their sum.",
    "square": "Write only a Python function square(x) that returns x squared.",
    "max_list": "Write only a Python function get_max(nums) that returns the maximum of a list.",
    "second_largest": "Write only a Python function second_largest(numbers) that returns the second-largest distinct number, handling duplicates correctly.",
    "unique_preserve_order": "Write only a Python function unique_preserve_order(items) that removes duplicates while preserving first occurrence order.",
    "normalize_slug": "Write only a Python function normalize_slug(text) that lowercases text, trims spaces, and replaces spaces with hyphens.",
    "palindrome": "Write only a Python function is_palindrome(text) that returns whether text is a palindrome.",
}

REFERENCES = {
    "add": [
        "def add(a, b):\n    return a + b",
        "def add(a, b):\n    return sum((a, b))",
        "def add(a, b):\n    result = b + a\n    return result",
    ],
    "square": [
        "def square(x):\n    return x * x",
        "def square(x):\n    return x ** 2",
        "def square(x):\n    result = x * x\n    return result",
    ],
    "max_list": [
        "def get_max(nums):\n    return max(nums)",
        "def get_max(nums):\n    return sorted(nums)[-1]",
        "def get_max(nums):\n    best = nums[0]\n    for value in nums[1:]:\n        if value > best:\n            best = value\n    return best",
    ],
    "second_largest": [
        "def second_largest(numbers):\n    return sorted(set(numbers))[-2]",
        "def second_largest(numbers):\n    unique = []\n    for value in numbers:\n        if value not in unique:\n            unique.append(value)\n    unique.sort()\n    return unique[-2]",
    ],
    "unique_preserve_order": [
        "def unique_preserve_order(items):\n    result = []\n    for item in items:\n        if item not in result:\n            result.append(item)\n    return result",
        "def unique_preserve_order(items):\n    seen = set()\n    result = []\n    for item in items:\n        if item not in seen:\n            seen.add(item)\n            result.append(item)\n    return result",
    ],
    "normalize_slug": [
        "def normalize_slug(text):\n    return text.strip().lower().replace(' ', '-')",
        "def normalize_slug(text):\n    cleaned = text.strip()\n    return cleaned.lower().replace(' ', '-')",
    ],
    "palindrome": [
        "def is_palindrome(text):\n    return text == text[::-1]",
        "def is_palindrome(text):\n    reversed_text = ''.join(reversed(text))\n    return reversed_text == text",
    ],
}

MUTANTS = {
    "add": [
        "def add(a, b):\n    return a - b",
        "def add(a, b):\n    return abs(a) + abs(b)",
        "def add(a, b):\n    return a + b + 1",
    ],
    "square": [
        "def square(x):\n    return x * 2",
        "def square(x):\n    return abs(x)",
        "def square(x):\n    return x ** 3",
    ],
    "max_list": [
        "def get_max(nums):\n    return nums[0]",
        "def get_max(nums):\n    return min(nums)",
        "def get_max(nums):\n    return max(nums[:-1])",
    ],
    "second_largest": [
        "def second_largest(numbers):\n    return sorted(numbers)[-2]",
        "def second_largest(numbers):\n    return sorted(set(numbers))[-1]",
        "def second_largest(numbers):\n    return numbers[1]",
    ],
    "unique_preserve_order": [
        "def unique_preserve_order(items):\n    return list(set(items))",
        "def unique_preserve_order(items):\n    return sorted(set(items))",
        "def unique_preserve_order(items):\n    return items",
    ],
    "normalize_slug": [
        "def normalize_slug(text):\n    return text.lower().replace(' ', '-')",
        "def normalize_slug(text):\n    return text.strip().replace(' ', '-')",
        "def normalize_slug(text):\n    return text.strip().lower()",
    ],
    "palindrome": [
        "def is_palindrome(text):\n    return True",
        "def is_palindrome(text):\n    return False",
        "def is_palindrome(text):\n    return text[0] == text[-1]",
    ],
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate code-verifier reference, mutant and adversarial rows.")
    parser.add_argument("--output", type=Path, default=Path("evals/code-verifier/code-verifier-holdout.jsonl"))
    args = parser.parse_args(argv)
    rows = build_rows()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "output": str(output)}))
    return 0


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(family: str, candidate: str, expected: bool, kind: str, index: int, prompt: str | None = None) -> None:
        task = prompt or PROMPTS[family]
        digest = hashlib.sha256(f"{family}\0{kind}\0{index}\0{task}\0{candidate}".encode()).hexdigest()[:16]
        rows.append(
            {
                "id": f"code_{digest}",
                "family": family,
                "kind": kind,
                "prompt": task,
                "candidate": candidate,
                "expected_accept": expected,
                "mutation_lineage": f"code_holdout_{family}_{kind}_{index}",
                "regression_split": "fresh_holdout",
                "schema_version": "code-verifier-holdout-v1",
            }
        )

    for family, candidates in REFERENCES.items():
        for index, candidate in enumerate(candidates):
            add(family, candidate, True, "reference", index)
    for family, candidates in MUTANTS.items():
        for index, candidate in enumerate(candidates):
            add(family, candidate, False, "mutant", index)

    debugging_prompt = (
        "This Python function should return the max of a list but has a bug:\n"
        "```python\ndef get_max(nums):\n    return nums[0]\n```\n"
        "Find and fix it. Return only corrected Python code."
    )
    add("max_list", "def get_max(nums):\n    return max(nums)", True, "debug_reference", 0, debugging_prompt)
    add("max_list", "def get_max(nums):\n    return nums[0]", False, "debug_mutant", 0, debugging_prompt)

    adversarial = [
        "import os\ndef add(a, b):\n    return a + b",
        "def add(a, b):\n    return open('/tmp/leak', 'w')",
        "def add(a, b):\n    return __import__('os').system('id')",
        "def add(a, b):\n    while True:\n        pass",
        "x = 1\ndef add(a, b):\n    return a + b",
        "def helper(x):\n    return x\n\ndef add(a, b):\n    return helper(a) + b",
        "def add(a):\n    return a",
        "def add(a, b):\n    pass",
    ]
    for index, candidate in enumerate(adversarial):
        add("add", candidate, False, "adversarial", index)

    # Frozen output from the independently generated 96-token E2B run. Tests were
    # authored separately; the truncated candidate must be rejected dynamically.
    e2b_prompt = (
        "Write a Python function second_largest(numbers) that takes a list of integers and returns the "
        "second largest unique integer in the list. If the list has fewer than 2 unique integers, return None."
    )
    e2b_candidate = '''def second_largest(numbers):
    """
    Finds the second largest unique integer in a list of integers.
    """
    if not numbers:
        return None
'''
    add("second_largest", e2b_candidate, False, "e2b_candidate", 0, e2b_prompt)
    rows[-1]["source_artifact"] = "reports/generated/amd-pod-e2b-regression-2000/e2b-candidates-96-contract-v2.jsonl"
    rows[-1]["source_task_id"] = "example_b6ce1f553765aa33d1d8"
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
