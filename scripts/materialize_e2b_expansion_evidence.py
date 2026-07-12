#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize traceable raw and post-contract Sprint 70 evidence.")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    source = ROOT / "reports/generated/e2b-expansion-v1/e2b.jsonl"
    raw_rows = _rows(source)
    by_id = {str(row["task_id"]): row for row in raw_rows}
    candidates = []
    for scope in ("development", "sealed"):
        candidates.extend(_rows(ROOT / f"evals/e2b-expansion-v1/adjudication/{scope}/candidates.jsonl"))
    candidate_ids = {str(row["task_id"]) for row in candidates}
    if not args.allow_partial and (len(by_id) != 2400 or candidate_ids != set(by_id)):
        raise ValueError("Complete evidence requires 2,400 inference and post-contract rows.")
    output = ROOT / "reports/generated/e2b-expansion-v1"
    raw_output = output / "e2b-raw.jsonl"
    post_output = output / "e2b-post-contract.jsonl"
    raw_payload = [{
        "schema_version": "e2b-expansion-raw-v1",
        "task_id": task_id,
        "prompt_sha256": row["prompt_sha256"],
        "raw_answer": row["answer"],
        "runtime_id": row.get("runtime_id"),
        "latency_ms": row.get("latency_ms"),
        "status": row.get("status", "success"),
    } for task_id, row in sorted(by_id.items())]
    post_payload = [{
        "schema_version": "e2b-expansion-post-contract-v1",
        "task_id": row["task_id"],
        "raw_answer": row["raw_answer"],
        "answer": row["answer"],
        "contract": row["contract"],
        "contract_idempotent": row["contract_idempotent"],
        "normalization_changed": row["normalization_changed"],
    } for row in sorted(candidates, key=lambda item: str(item["task_id"]))]
    _write(raw_output, raw_payload)
    _write(post_output, post_payload)
    report = {
        "raw_rows": len(raw_payload),
        "post_contract_rows": len(post_payload),
        "raw_sha256": hashlib.sha256(raw_output.read_bytes()).hexdigest(),
        "post_contract_sha256": hashlib.sha256(post_output.read_bytes()).hexdigest(),
        "complete": len(raw_payload) == len(post_payload) == 2400,
    }
    print(json.dumps(report, sort_keys=True))
    return 0


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def _write(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
