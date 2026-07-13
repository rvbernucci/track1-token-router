#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import sys
from threading import Lock
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.dataset_forge.providers import ProviderError, provider_from_env
from router.orchestration.local_adjudication import build_local_adjudication_evidence
from scripts.adjudicate_e2b_regression_v2 import _mechanical


SCHEMA_VERSION = "s81-e2b-population-adjudication-v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Mechanically prepare and Antigravity-judge Sprint 81 E2B output.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--judge-agy", action="store_true")
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not any((args.prepare, args.judge_agy, args.summarize)):
        parser.error("choose --prepare, --judge-agy or --summarize")
    if args.batch_size < 1 or args.workers < 1:
        parser.error("batch size and workers must be positive")

    result: dict[str, Any] = {}
    if args.prepare:
        result["prepare"] = prepare(args.input, args.output_root)
    if args.judge_agy:
        result["judge_agy"] = judge_agy(args.output_root, args.batch_size, args.workers)
    if args.summarize:
        result["summary"] = summarize(args.output_root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def prepare(input_path: Path, output_root: Path) -> dict[str, Any]:
    rows = _rows(input_path)
    if len(rows) != 4400 or len({row["task_id"] for row in rows}) != 4400:
        raise ValueError(f"Expected 4,400 unique E2B rows, found {len(rows)}")
    candidates = []
    for row in sorted(rows, key=lambda item: item["task_id"]):
        answer = str(row["post_contract_answer"])
        prompt = str(row["prompt"])
        contract = dict(row["answer_contract"])
        contract_valid = bool(contract.get("valid"))
        envelope = TaskEnvelope(id=str(row["task_id"]), input_text=prompt)
        local_evidence = build_local_adjudication_evidence(envelope, answer).to_dict()
        reference = {
            "reference_answer": str(row["reference_answer"]),
            "output_shape": row.get("output_shape"),
        }
        mechanical = _mechanical(
            reference,
            answer,
            contract_valid,
            str(row["category"]),
            local_evidence=local_evidence,
        )
        candidates.append({
            "schema_version": SCHEMA_VERSION,
            "candidate_id": "s81-" + str(row["task_id"]),
            "task_id": row["task_id"],
            "role": row["role"],
            "category": row["category"],
            "prompt": prompt,
            "answer": answer,
            "reference_answer": row["reference_answer"],
            "reference_rubric": row["reference_rubric"],
            "output_shape": row.get("output_shape"),
            "answer_contract": contract,
            "mechanical": mechanical,
            "local_verifier_evidence": local_evidence,
            "candidate_sha256": hashlib.sha256(answer.encode()).hexdigest(),
            "latency_ms": row.get("latency_ms"),
        })
    queue = [row for row in candidates if not row["mechanical"]["hard"]]
    output_root.mkdir(parents=True, exist_ok=True)
    _write(output_root / "candidates.jsonl", candidates)
    _write(output_root / "agy-queue.jsonl", queue)
    return {
        "rows": len(candidates),
        "mechanical": len(candidates) - len(queue),
        "agy_queue": len(queue),
        "mechanical_verdicts": dict(Counter(row["mechanical"]["verdict"] for row in candidates if row["mechanical"]["hard"])),
    }


def judge_agy(output_root: Path, batch_size: int, workers: int) -> dict[str, Any]:
    queue = _rows(output_root / "agy-queue.jsonl")
    output_path = output_root / "agy-judgments.jsonl"
    completed = {row["candidate_id"] for row in _rows(output_path)}
    pending = [row for row in queue if row["candidate_id"] not in completed]
    batches = [pending[index : index + batch_size] for index in range(0, len(pending), batch_size)]
    provider = provider_from_env("agy", role="s81_e2b_correctness_judge", max_tokens=4096)
    provider._verify_model()
    lock = Lock()
    written = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_judge_batch, provider, batch): batch for batch in batches}
        for future in as_completed(futures):
            batch = futures[future]
            try:
                judgments = future.result()
            except (ProviderError, ValueError, OSError) as exc:
                failed += 1
                print(json.dumps({"failed_ids": [row["candidate_id"] for row in batch], "error": str(exc)}), file=sys.stderr)
                continue
            with lock, output_path.open("a", encoding="utf-8") as stream:
                for judgment in judgments:
                    stream.write(json.dumps(judgment, ensure_ascii=False, sort_keys=True) + "\n")
            written += len(judgments)
            if written % (batch_size * 10) == 0:
                print(json.dumps({"judged": written, "remaining": len(pending) - written}), flush=True)
    return {"queue": len(queue), "resumed": len(completed), "written": written, "failed_batches": failed}


def _judge_batch(provider: Any, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    invocation = provider.invoke(
        prompt=_judge_prompt(rows),
        response_schema=_judge_schema(len(rows)),
        role="s81_e2b_correctness_judge",
    )
    items = invocation.payload.get("items")
    if not isinstance(items, list) or len(items) != len(rows):
        raise ValueError("Antigravity returned the wrong judgment count.")
    expected = {str(row["candidate_id"]) for row in rows}
    returned = {str(item.get("candidate_id")) for item in items if isinstance(item, Mapping)}
    if returned != expected or len(returned) != len(items):
        raise ValueError("Antigravity changed, omitted or duplicated candidate IDs.")
    result = []
    for item in items:
        verdict = str(item.get("verdict"))
        confidence = item.get("confidence")
        if verdict not in {"correct", "incorrect", "uncertain"}:
            raise ValueError("Antigravity returned an invalid verdict.")
        if not isinstance(confidence, int) or isinstance(confidence, bool) or not 0 <= confidence <= 100:
            raise ValueError("Antigravity returned invalid confidence.")
        result.append({
            "schema_version": SCHEMA_VERSION,
            "candidate_id": item["candidate_id"],
            "verdict": verdict,
            "format_valid": bool(item.get("format_valid")),
            "confidence": confidence,
            "rationale": str(item.get("rationale") or ""),
            "judge_provider": "agy",
            "judge_model": invocation.provenance.model,
            "request_id": invocation.provenance.request_id,
        })
    return result


def summarize(output_root: Path) -> dict[str, Any]:
    candidates = {row["candidate_id"]: row for row in _rows(output_root / "candidates.jsonl")}
    judgments = {row["candidate_id"]: row for row in _rows(output_root / "agy-judgments.jsonl")}
    labels = []
    for candidate in candidates.values():
        mechanical = candidate["mechanical"]
        if mechanical["hard"]:
            verdict, source, confidence = mechanical["verdict"], "mechanical", 100
        elif candidate["candidate_id"] in judgments:
            judgment = judgments[candidate["candidate_id"]]
            verdict, source, confidence = judgment["verdict"], "agy", judgment["confidence"]
        else:
            verdict, source, confidence = "uncertain", "missing", 0
        labels.append({
            "task_id": candidate["task_id"],
            "role": candidate["role"],
            "category": candidate["category"],
            "verdict": verdict,
            "correct": verdict == "correct",
            "source": source,
            "confidence": confidence,
        })
    _write(output_root / "labels.jsonl", labels)
    by_category: dict[str, Counter[str]] = defaultdict(Counter)
    for row in labels:
        by_category[row["category"]][row["verdict"]] += 1
        by_category[row["category"]]["total"] += 1
    totals = Counter(row["verdict"] for row in labels)
    return {
        "rows": len(labels),
        "correct": totals["correct"],
        "incorrect": totals["incorrect"],
        "uncertain": totals["uncertain"],
        "accuracy_lower_bound": totals["correct"] / len(labels),
        "by_category": {key: dict(value) for key, value in sorted(by_category.items())},
    }


def _judge_prompt(rows: Sequence[Mapping[str, Any]]) -> str:
    visible = [{
        "candidate_id": row["candidate_id"],
        "task": row["prompt"],
        "candidate_answer": row["answer"],
        "reference_answer": row["reference_answer"],
        "reference_rubric": row["reference_rubric"],
        "output_shape": row["output_shape"],
    } for row in rows]
    return (
        "Judge whether each candidate answer satisfies its quoted task and reference rubric. "
        "Correct means fully acceptable, not stylistically best. Use uncertain only when the rubric truly cannot decide. "
        "Check required output format separately. Return concise rationales without chain-of-thought.\n\n"
        + json.dumps(visible, ensure_ascii=False, separators=(",", ":"))
    )


def _judge_schema(count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {"items": {
            "type": "array",
            "minItems": count,
            "maxItems": count,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["candidate_id", "verdict", "format_valid", "confidence", "rationale"],
                "properties": {
                    "candidate_id": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["correct", "incorrect", "uncertain"]},
                    "format_valid": {"type": "boolean"},
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "rationale": {"type": "string"},
                },
            },
        }},
    }


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def _write(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    os.environ.setdefault("DATASET_AGY_EXPECTED_EMAIL", "rvbernucci@gmail.com")
    raise SystemExit(main())
