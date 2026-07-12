#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.build_router_ml_v3_ledger import _contract_features, _proof_features


def rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in values), encoding="utf-8")


def build(
    base_ledger: Path,
    candidates_path: Path,
    judgment_paths: list[Path],
    output: Path,
    protected_output: Path,
) -> dict[str, Any]:
    base = {row["task_id"]: row for row in rows(base_ledger)}
    candidates = {row["task_id"]: row for row in rows(candidates_path)}
    judgments = {row["candidate_id"]: row for path in judgment_paths for row in rows(path)}
    if set(base) != set(candidates) or len(base) != 4400:
        raise ValueError(f"ML join requires 4,400 rows: base={len(base)} candidates={len(candidates)}")
    ledger: list[dict[str, Any]] = []
    protected: list[dict[str, Any]] = []
    evidence = Counter()
    positives = Counter()
    for task_id in sorted(base):
        original, candidate = base[task_id], candidates[task_id]
        mechanical = candidate["mechanical"]["verdict"]
        if mechanical in {"correct", "incorrect"}:
            verdict, source = mechanical, "mechanical"
        else:
            judgment = judgments.get(candidate["id"])
            verdict = str(judgment.get("verdict")) if judgment else "uncertain"
            source = str(judgment.get("judge_model")) if judgment else "missing_judge"
        binary = int(verdict == "correct")
        updated = json.loads(json.dumps(original))
        updated["features"].update(_contract_features(candidate))
        updated["features"].update(_proof_features(candidate))
        updated["targets"]["e2b"] = None if original["role"] == "protected_holdout" else binary
        updated["provenance"].update(
            {
                "e2b_model": candidate["engine_version"],
                "label_source": None if original["role"] == "protected_holdout" else source,
                "prompt_version": candidate["prompt_version"],
            }
        )
        ledger.append(updated)
        evidence[source] += 1
        positives[original["role"]] += binary
        if original["role"] == "protected_holdout":
            protected.append(
                {
                    "task_id": task_id,
                    "binary_label": binary,
                    "verdict": verdict,
                    "evidence_source": source,
                }
            )
    write(output, ledger)
    write(protected_output, protected)
    summary = {
        "rows": len(ledger),
        "protected_rows": len(protected),
        "positive_by_role": dict(positives),
        "evidence": dict(evidence),
        "missing_judges": evidence["missing_judge"],
    }
    if summary["missing_judges"]:
        raise ValueError(f"Missing semantic judgments: {summary['missing_judges']}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ledger", type=Path, default=Path("evals/router-ml-v3/ledger.jsonl"))
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--judgments", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protected-output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.base_ledger, args.candidates, args.judgments, args.output, args.protected_output),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
