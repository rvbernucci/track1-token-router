#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.orchestration.local_adjudication import build_local_adjudication_evidence
from scripts.adjudicate_e2b_regression_v2 import _mechanical


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in values),
        encoding="utf-8",
    )


def prepare(source: Path, output: Path, *, require_full: bool = True) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for row in rows(source):
        answer = str(row.get("post_contract_answer") or "")
        task = TaskEnvelope(id=str(row["task_id"]), input_text=str(row["prompt"]))
        evidence = build_local_adjudication_evidence(task, answer).to_dict()
        reference = {
            "reference_answer": row["reference_answer"],
            "reference_rubric": row["reference_rubric"],
            "output_shape": row.get("output_shape"),
        }
        contract = row.get("answer_contract") or {}
        mechanical = _mechanical(
            reference,
            answer,
            bool(contract.get("valid")),
            str(row["category"]),
            local_evidence=evidence,
        )
        candidates.append(
            {
                **row,
                "id": f"e2b-contract-{row['task_id']}",
                "task_text": row["prompt"],
                "answer": answer,
                "engine": "gemma4-e2b",
                "engine_version": "gemma-4-E2B-it-litert-lm-6664aee5-contract-v1",
                "local_verifier_evidence": evidence,
                "mechanical": mechanical,
            }
        )
    expected = 4400 if require_full else len(candidates)
    if len(candidates) != expected or len({row["task_id"] for row in candidates}) != expected:
        raise ValueError("Contract adjudication requires exactly 4,400 unique tasks")
    uncertain = [row for row in candidates if row["mechanical"]["verdict"] == "uncertain"]
    codex = [row for row in uncertain if int(hashlib.sha256(row["id"].encode()).hexdigest(), 16) % 2 == 0]
    agy = [row for row in uncertain if row not in codex]
    write(output / "candidates.jsonl", candidates)
    write(output / "judge-codex.jsonl", codex)
    write(output / "judge-agy.jsonl", agy)
    for role in ("fit", "calibration", "protected_holdout"):
        write(output / f"candidates-{role}.jsonl", [row for row in candidates if row["role"] == role])
    summary = {
        "rows": len(candidates),
        "roles": Counter(row["role"] for row in candidates),
        "mechanical": Counter(row["mechanical"]["verdict"] for row in candidates),
        "judge_codex": len(codex),
        "judge_agy": len(agy),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=dict) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output, require_full=not args.allow_partial), sort_keys=True, default=dict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
