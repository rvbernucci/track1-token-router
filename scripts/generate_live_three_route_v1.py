#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_fireworks_pareto_v2 import (
    CATEGORIES, _codegen, _debug, _factual, _logic, _ner, _sentiment, _summary,
)


def main() -> int:
    rows = generate()
    target = ROOT / "evals/live-three-route-v1/tasks.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "live-three-route-v1-manifest",
        "rows": len(rows),
        "category_counts": dict(sorted(Counter(row["category"] for row in rows).items())),
        "expected_route_counts": dict(sorted(Counter(row["expected_route"] for row in rows).items())),
        "tasks_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "labels_frozen_before_inference": True,
    }
    (target.parent / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0


def generate() -> list[dict]:
    factories = {
        "factual_qa": _factual, "sentiment": _sentiment, "summarization": _summary,
        "ner": _ner, "code_debugging": _debug, "logic_puzzle": _logic, "code_generation": _codegen,
    }
    rows = []
    for category in CATEGORIES:
        for offset in range(12):
            index = 300 + offset
            difficulty = ("easy", "medium", "hard")[offset % 3]
            if category == "math_reasoning":
                left, right = 700 + offset, 30 + offset
                prompt = f"Compute {left} + {right}. Return only the number."
                validator, shape, expected_route = {"type": "number_exact", "expected": left + right}, "number", "deterministic"
            else:
                prompt, validator, _, shape = factories[category](index, difficulty)
                expected_route = "e2b" if category == "sentiment" else "fireworks"
            task_id = f"live_{category}_{offset:02d}"
            rows.append({
                "task_id": task_id, "prompt": prompt, "category": category,
                "difficulty": difficulty, "output_shape": shape, "validator": validator,
                "expected_route": expected_route, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            })
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
