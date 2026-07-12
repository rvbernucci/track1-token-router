#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.dataset_forge.providers import FireworksDatasetProvider, ProviderError
from router.dataset_forge.storage import AppendOnlyJsonl
from scripts.adjudicate_e2b_expansion import _judge_prompt, _judge_schema, _load_env


KIMI = "accounts/fireworks/models/kimi-k2p7-code"
MINIMAX = "accounts/fireworks/models/minimax-m3"


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently re-audit a deterministic 10% expansion label sample.")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--consolidate", action="store_true")
    parser.add_argument("--include-holdout", action="store_true")
    parser.add_argument("--batch-size", type=int, default=6)
    args = parser.parse_args()
    _load_env([Path(".env.fireworks.local")])
    result = {}
    if args.prepare:
        result["prepare"] = prepare(include_holdout=args.include_holdout)
    if args.judge:
        result["judge"] = judge(batch_size=args.batch_size)
    if args.consolidate:
        result["consolidate"] = consolidate()
    print(json.dumps(result, sort_keys=True))
    return 0


def prepare(*, include_holdout: bool) -> dict[str, Any]:
    metadata = _keyed(ROOT / "evals/e2b-expansion-v1/metadata.jsonl")
    scopes = ["development"] + (["sealed"] if include_holdout else [])
    candidates = {}
    labels = {}
    for scope in scopes:
        base = ROOT / f"evals/e2b-expansion-v1/adjudication/{scope}"
        candidates.update({row["task_id"]: row for row in _rows(base / "candidates.jsonl")})
        labels.update({row["task_id"]: row for row in _rows(base / "labels.jsonl")})
    complete = [task_id for task_id in sorted(set(candidates) & set(labels)) if labels[task_id]["final_label"] != "uncertain"]
    strata = {
        "mechanical": [task_id for task_id in complete if labels[task_id]["evidence_source"] == "mechanical"],
        "judge": [task_id for task_id in complete if labels[task_id]["evidence_source"] != "mechanical"],
    }
    selected = []
    for stratum, task_ids in strata.items():
        ordered = sorted(task_ids, key=lambda task_id: hashlib.sha256(f"s70-audit:{task_id}".encode()).hexdigest())
        selected.extend((stratum, task_id) for task_id in ordered[:math.ceil(len(ordered) * 0.10)])
    queue = []
    for stratum, task_id in selected:
        candidate = candidates[task_id]
        original_model = str(metadata[task_id]["provider_model"])
        audit_model = MINIMAX if "kimi" in original_model.casefold() else KIMI
        queue.append({
            **candidate,
            "audit_stratum": stratum,
            "original_label": labels[task_id]["final_label"],
            "original_evidence_source": labels[task_id]["evidence_source"],
            "generator_model": original_model,
            "audit_model": audit_model,
        })
    output = ROOT / "reports/generated/e2b-expansion-v1/label-audit-queue.jsonl"
    _write(output, queue)
    return {
        "population": len(complete), "selected": len(queue),
        "by_stratum": dict(sorted(Counter(row["audit_stratum"] for row in queue).items())),
        "holdout_opened": include_holdout,
    }


def judge(*, batch_size: int) -> dict[str, Any]:
    api_key = os.getenv("FIREWORKS_API_KEY")
    if not api_key:
        raise ValueError("FIREWORKS_API_KEY is required for the independent label audit.")
    queue = _rows(ROOT / "reports/generated/e2b-expansion-v1/label-audit-queue.jsonl")
    output = AppendOnlyJsonl(ROOT / "reports/generated/e2b-expansion-v1/label-audit-judgments.jsonl", id_field="id")
    done = {str(row["candidate_id"]) for row in output.read_all()}
    completed = failures = 0
    for model in (KIMI, MINIMAX):
        provider = FireworksDatasetProvider(
            api_key=api_key,
            base_url=os.getenv("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"),
            model=model,
            max_tokens=4096,
        )
        eligible = [row for row in queue if row["audit_model"] == model and row["id"] not in done]
        for start in range(0, len(eligible), batch_size):
            batch = eligible[start:start + batch_size]
            try:
                invocation = provider.invoke(
                    prompt=_judge_prompt(batch), response_schema=_judge_schema(len(batch)), role="e2b_expansion_label_audit",
                )
                items = invocation.payload["items"]
                if len(items) != len(batch):
                    raise ProviderError("Label audit returned an invalid item count.")
            except (KeyError, ProviderError):
                failures += len(batch)
                continue
            for item in items:
                output.append_unique({
                    "id": hashlib.sha256(f"audit:{item['candidate_id']}:{model}".encode()).hexdigest(),
                    "candidate_id": item["candidate_id"], "audit_model": model,
                    "verdict": item["verdict"], "rationale": item["rationale"],
                    "request_id": invocation.provenance.request_id,
                })
                completed += 1
    return {"completed": completed, "failures": failures}


def consolidate() -> dict[str, Any]:
    queue = {row["id"]: row for row in _rows(ROOT / "reports/generated/e2b-expansion-v1/label-audit-queue.jsonl")}
    judgments = {row["candidate_id"]: row for row in _rows(ROOT / "reports/generated/e2b-expansion-v1/label-audit-judgments.jsonl")}
    audited = [{
        "task_id": row["task_id"], "stratum": row["audit_stratum"],
        "original_label": row["original_label"], "audit_label": judgments[candidate_id]["verdict"],
        "agreement": row["original_label"] == judgments[candidate_id]["verdict"],
        "generator_model": row["generator_model"], "audit_model": row["audit_model"],
    } for candidate_id, row in queue.items() if candidate_id in judgments]
    by_stratum = {}
    for stratum in ("mechanical", "judge"):
        cohort = [row for row in audited if row["stratum"] == stratum]
        by_stratum[stratum] = {
            "audited": len(cohort), "agreed": sum(row["agreement"] for row in cohort),
            "agreement_rate": sum(row["agreement"] for row in cohort) / len(cohort) if cohort else 0.0,
        }
    report = {
        "selected": len(queue), "audited": len(audited), "missing": len(queue) - len(audited),
        "by_stratum": by_stratum,
    }
    target = ROOT / "reports/generated/e2b-expansion-v1/label-audit.json"
    target.write_text(json.dumps({**report, "rows": audited}, indent=2, sort_keys=True) + "\n")
    return report


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def _keyed(path: Path) -> dict[str, dict[str, Any]]:
    return {str(row["task_id"]): row for row in _rows(path)}


def _write(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
