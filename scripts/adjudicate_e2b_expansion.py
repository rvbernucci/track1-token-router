#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.dataset_forge.storage import AppendOnlyJsonl
from router.dataset_forge.providers import ProviderError, provider_from_env
from router.orchestration.final_validator import apply_answer_contract
from router.orchestration.local_adjudication import build_local_adjudication_evidence
from scripts.adjudicate_e2b_regression_v2 import _mechanical


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and adjudicate Sprint 70 E2B expansion outcomes.")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--consolidate", action="store_true")
    parser.add_argument("--include-holdout", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--max-batches", type=int)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--judge-provider", choices=("agy", "fireworks", "codex"))
    parser.add_argument("--disagreements", action="store_true")
    parser.add_argument("--env-file", action="append", type=Path)
    args = parser.parse_args()
    if not any((args.prepare, args.judge, args.consolidate)):
        parser.error("choose --prepare, --judge or --consolidate")
    _load_env(args.env_file or [Path(".env.dataset-forge.local"), Path(".env.fireworks.local")])
    result = {}
    if args.prepare:
        result["prepare"] = prepare(include_holdout=args.include_holdout, allow_partial=args.allow_partial)
    if args.judge:
        result["judge"] = judge(
            include_holdout=args.include_holdout, batch_size=args.batch_size, max_batches=args.max_batches,
            provider_names=(args.judge_provider,) if args.judge_provider else ("agy", "fireworks", "codex"),
            disagreements_only=args.disagreements,
        )
    if args.consolidate:
        result["consolidate"] = consolidate(include_holdout=args.include_holdout)
    print(json.dumps(result, sort_keys=True))
    return 0


def prepare(*, include_holdout: bool, allow_partial: bool = False) -> dict[str, Any]:
    corpus = ROOT / "evals/e2b-expansion-v1"
    inference = ROOT / "reports/generated/e2b-expansion-v1"
    metadata = _keyed(corpus / "metadata.jsonl")
    assessments = _keyed(inference / "functiongemma.jsonl")
    answers = _keyed(inference / "e2b.jsonl")
    splits = ["train", "calibration"] + (["final_holdout"] if include_holdout else [])
    candidates = []
    for split in splits:
        directory = "sealed/tasks" if split == "final_holdout" else "splits"
        ref_dir = "sealed/references" if split == "final_holdout" else "references"
        tasks = _keyed(corpus / directory / f"{split}.jsonl")
        refs = _keyed(corpus / ref_dir / f"{split}.jsonl")
        if set(tasks) != set(refs) or (not allow_partial and not set(tasks) <= set(answers)):
            raise ValueError(f"Expansion inference is incomplete for {split}.")
        available_ids = set(tasks) & set(answers)
        for task_id in sorted(available_ids):
            prompt = str(tasks[task_id]["prompt"])
            raw = str(answers[task_id]["answer"])
            envelope = TaskEnvelope(id=task_id, input_text=prompt)
            contract = apply_answer_contract(envelope, raw)
            normalized = contract.answer if contract.valid else raw.strip()
            repeated = apply_answer_contract(envelope, normalized)
            idempotent = contract.valid and repeated.valid and repeated.answer == normalized
            effective_valid = contract.valid and idempotent
            evidence = build_local_adjudication_evidence(envelope, normalized).to_dict()
            reference = refs[task_id]
            mechanical = _mechanical(
                reference, normalized, effective_valid, metadata[task_id]["category"],
                local_evidence=evidence,
            )
            candidates.append({
                "id": f"s70-candidate-{task_id}", "task_id": task_id, "split": split,
                "category": metadata[task_id]["category"], "difficulty": metadata[task_id]["difficulty"],
                "prompt": prompt, "raw_answer": raw, "answer": normalized,
                "reference_answer": reference["reference_answer"],
                "reference_rubric": reference["reference_rubric"],
                "output_shape": reference["output_shape"], "evidence_mode": reference["evidence_mode"],
                "contract": {**contract.to_dict(), "effective_valid": effective_valid},
                "contract_idempotent": idempotent, "normalization_changed": normalized != raw.strip(),
                "mechanical": mechanical, "local_verifier_evidence": evidence,
                "functiongemma_assessment": assessments.get(task_id, {}).get("assessment"),
                "assessment_valid": isinstance(assessments.get(task_id, {}).get("assessment"), Mapping),
                "generator_provider": metadata[task_id]["provider"],
                "eligible_judges": metadata[task_id]["eligible_judges"],
            })
    development = [row for row in candidates if row["split"] != "final_holdout"]
    sealed = [row for row in candidates if row["split"] == "final_holdout"]
    _write(ROOT / "evals/e2b-expansion-v1/adjudication/development/candidates.jsonl", development)
    _write(ROOT / "evals/e2b-expansion-v1/adjudication/development/judge-queue.jsonl", [row for row in development if row["mechanical"]["verdict"] == "uncertain"])
    if include_holdout:
        _write(ROOT / "evals/e2b-expansion-v1/adjudication/sealed/candidates.jsonl", sealed)
        _write(ROOT / "evals/e2b-expansion-v1/adjudication/sealed/judge-queue.jsonl", [row for row in sealed if row["mechanical"]["verdict"] == "uncertain"])
    return {
        "rows": len(candidates), "mechanical": dict(sorted(Counter(row["mechanical"]["verdict"] for row in candidates).items())),
        "judge_queue": sum(row["mechanical"]["verdict"] == "uncertain" for row in candidates),
        "contract_invalid": sum(not row["contract"]["effective_valid"] for row in candidates),
        "holdout_opened": include_holdout,
        "partial": allow_partial,
    }


def judge(
    *, include_holdout: bool, batch_size: int, max_batches: int | None,
    provider_names: Sequence[str] = ("agy", "fireworks", "codex"),
    disagreements_only: bool = False,
) -> dict[str, Any]:
    if batch_size < 1:
        raise ValueError("Judge batch size must be positive.")
    roots = [ROOT / "evals/e2b-expansion-v1/adjudication/development"]
    if include_holdout:
        roots.append(ROOT / "evals/e2b-expansion-v1/adjudication/sealed")
    providers = {
        name: provider_from_env(name, role="e2b_expansion_judge", max_tokens=4096)
        for name in provider_names
    }
    attempted = completed = 0
    for root in roots:
        queue = _disagreement_candidates(root) if disagreements_only else _rows(root / "judge-queue.jsonl")
        for provider_name, provider in providers.items():
            output = AppendOnlyJsonl(root / f"judgments-{provider_name}.jsonl", id_field="id")
            done = {
                row["candidate_id"] for row in output.read_all()
                if row.get("judge_model")
            }
            eligible = [
                row for row in queue
                if provider_name in row["eligible_judges"] and row["id"] not in done
            ]
            for start in range(0, len(eligible), batch_size):
                if max_batches is not None and attempted >= max_batches:
                    return {"attempted_batches": attempted, "completed_judgments": completed, "paused": True}
                batch = eligible[start:start + batch_size]
                attempted += 1
                try:
                    invocation = provider.invoke(
                        prompt=_judge_prompt(batch), response_schema=_judge_schema(len(batch)), role="e2b_expansion_judge",
                    )
                    items = invocation.payload.get("items")
                    if not isinstance(items, list) or len(items) != len(batch):
                        raise ProviderError("Expansion judge returned an invalid item count.")
                    expected = {row["id"] for row in batch}
                    if {str(item.get("candidate_id")) for item in items if isinstance(item, Mapping)} != expected:
                        raise ProviderError("Expansion judge changed candidate IDs.")
                    if any(str(item.get("verdict")) not in {"correct", "incorrect"} for item in items):
                        raise ProviderError("Expansion judge verdict is invalid.")
                except ProviderError as exc:
                    AppendOnlyJsonl(root / f"judgment-failures-{provider_name}.jsonl").append_unique({
                        "id": hashlib.sha256(f"{provider_name}:{start}:{exc}".encode()).hexdigest(),
                        "provider": provider_name, "candidate_ids": [row["id"] for row in batch],
                        "error": str(exc), "retriable": True,
                    })
                    continue
                for item in items:
                    verdict = str(item["verdict"])
                    output.append_unique({
                        "id": hashlib.sha256(f"{item['candidate_id']}:{invocation.provenance.model}".encode()).hexdigest(),
                        "candidate_id": item["candidate_id"], "verdict": verdict,
                        "rationale": str(item["rationale"]), "judge_provider": provider_name,
                        "judge_model": invocation.provenance.model,
                        "request_id": invocation.provenance.request_id,
                    })
                    completed += 1
    return {"attempted_batches": attempted, "completed_judgments": completed, "paused": False}


def _disagreement_candidates(root: Path) -> list[dict[str, Any]]:
    candidates = {row["id"]: row for row in _rows(root / "candidates.jsonl")}
    judgments: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for provider in ("agy", "fireworks", "codex"):
        for row in _rows(root / f"judgments-{provider}.jsonl"):
            judgments[str(row["candidate_id"])].append(row)
    result = []
    for candidate_id, candidate in candidates.items():
        votes = judgments[candidate_id]
        if len({row["judge_model"] for row in votes}) >= 2 and len({row["verdict"] for row in votes}) > 1:
            result.append({**candidate, "eligible_judges": [candidate["generator_provider"]]})
    return result


def consolidate(*, include_holdout: bool) -> dict[str, Any]:
    roots = [ROOT / "evals/e2b-expansion-v1/adjudication/development"]
    if include_holdout:
        roots.append(ROOT / "evals/e2b-expansion-v1/adjudication/sealed")
    all_labels = []
    for root in roots:
        candidates = _rows(root / "candidates.jsonl")
        judgments: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for provider in ("agy", "fireworks", "codex"):
            for row in _rows(root / f"judgments-{provider}.jsonl"):
                judgments[str(row["candidate_id"])].append(row)
        labels = []
        for row in candidates:
            mechanical = row["mechanical"]
            votes = judgments[row["id"]]
            if mechanical["hard"]:
                verdict, source = mechanical["verdict"], "mechanical"
            elif len(votes) >= 3 and len({vote["judge_model"] for vote in votes}) >= 3:
                correct_votes = sum(vote["verdict"] == "correct" for vote in votes)
                incorrect_votes = sum(vote["verdict"] == "incorrect" for vote in votes)
                verdict = "correct" if correct_votes > incorrect_votes else "incorrect"
                source = "judge_adjudication"
            elif len(votes) >= 2 and len({vote["verdict"] for vote in votes}) == 1:
                verdict, source = votes[0]["verdict"], "judge_consensus"
            else:
                verdict, source = "uncertain", "missing_or_disagreeing_judges"
            labels.append({
                "task_id": row["task_id"], "split": row["split"], "category": row["category"],
                "difficulty": row["difficulty"], "final_label": verdict,
                "binary_label": int(verdict == "correct"), "evidence_source": source,
                "contract_valid": row["contract"]["effective_valid"],
                "assessment_valid": row["assessment_valid"],
                "judge_models": [vote["judge_model"] for vote in votes],
                "judge_verdicts": [vote["verdict"] for vote in votes],
            })
        _write(root / "labels.jsonl", labels)
        all_labels.extend(labels)
    # The canonical ledger imports this path only after development labels exist.
    development_labels = ROOT / "evals/e2b-expansion-v1/adjudication/development/labels.jsonl"
    canonical = ROOT / "reports/generated/e2b-expansion-v1/labels.jsonl"
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in all_labels),
        encoding="utf-8",
    )
    return {
        "rows": len(all_labels), "correct": sum(row["binary_label"] for row in all_labels),
        "unresolved": sum(row["final_label"] == "uncertain" for row in all_labels),
        "evidence_sources": dict(sorted(Counter(row["evidence_source"] for row in all_labels).items())),
        "holdout_opened": include_holdout,
    }


def _judge_prompt(rows: Sequence[Mapping[str, Any]]) -> str:
    visible = [{
        "candidate_id": row["id"], "task": row["prompt"], "candidate_answer": row["answer"],
        "reference_answer": row["reference_answer"], "reference_rubric": row["reference_rubric"],
    } for row in rows]
    return (
        "Judge semantic correctness only. Apply the task and rubric, not stylistic preference. "
        "Return correct only when the candidate fully satisfies the task. Do not expose chain-of-thought.\n\n"
        + json.dumps(visible, ensure_ascii=False, sort_keys=True)
    )


def _judge_schema(count: int) -> dict[str, Any]:
    return {
        "type": "object", "additionalProperties": False, "required": ["items"],
        "properties": {"items": {"type": "array", "minItems": count, "maxItems": count, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["candidate_id", "verdict", "rationale"],
            "properties": {"candidate_id": {"type": "string"},
                "verdict": {"type": "string", "enum": ["correct", "incorrect"]},
                "rationale": {"type": "string"}},
        }}},
    }


def _load_env(paths: Sequence[Path]) -> None:
    for path in paths:
        resolved = path if path.is_absolute() else ROOT / path
        if not resolved.is_file():
            continue
        for line in resolved.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def _keyed(path: Path) -> dict[str, dict[str, Any]]:
    return {str(row["task_id"]): row for row in _rows(path)}


def _write(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
