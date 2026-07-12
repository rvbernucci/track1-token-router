#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCORES = (
    "deterministic_fit", "reasoning_demand", "knowledge_uncertainty",
    "generation_demand", "format_complexity",
)


def main() -> int:
    path = ROOT / "reports/generated/e2b-expansion-v1/regression-ledger.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = analyze(rows)
    output = ROOT / "reports/generated/e2b-expansion-v1/functiongemma-score-collapse.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


def analyze(rows: list[dict]) -> dict:
    by_intent = {}
    for intent in sorted({row["predicted_intent"] for row in rows if row["assessment_valid"]}):
        cohort = [row for row in rows if row["assessment_valid"] and row["predicted_intent"] == intent]
        vectors = [tuple(row["scores"][name] for name in SCORES) for row in cohort]
        counts = Counter(vectors)
        entropy = -sum((count / len(vectors)) * math.log2(count / len(vectors)) for count in counts.values())
        dominant = counts.most_common(1)[0][1] / len(vectors)
        by_intent[intent] = {
            "rows": len(cohort), "unique_score_vectors": len(counts),
            "score_vector_entropy_bits": entropy, "dominant_vector_share": dominant,
            "collapse_warning": len(counts) < 8 or dominant >= 0.40,
        }
    return {
        "schema_version": "functiongemma-score-collapse-v1", "rows": len(rows),
        "by_intent": by_intent,
        "retraining_indicated": any(item["collapse_warning"] for item in by_intent.values()),
        "policy": "Retrain only when collapse persists after mechanical-feature enrichment and category calibration.",
    }


if __name__ == "__main__":
    raise SystemExit(main())
