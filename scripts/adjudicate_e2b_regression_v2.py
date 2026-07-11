#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.orchestration.final_validator import apply_answer_contract
from router.orchestration.local_adjudication import build_local_adjudication_evidence


SCHEMA = "e2b-regression-v2-adjudication-v1"
SPLITS = ("train", "validation", "final_holdout")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare, consolidate and verify E2B V2 adjudication.")
    parser.add_argument("--root", type=Path, default=Path("evals/e2b-regression-v2-adjudication"))
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--consolidate", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = _absolute(args.root)
    if args.prepare:
        print(json.dumps(prepare(root), sort_keys=True))
    if args.consolidate:
        print(json.dumps(consolidate(root), sort_keys=True))
    if args.check:
        print(json.dumps(check(root), sort_keys=True))
    if not any((args.prepare, args.consolidate, args.check)):
        parser.error("choose --prepare, --consolidate or --check")
    return 0


def prepare(output: Path) -> dict[str, Any]:
    corpus = ROOT / "evals/e2b-regression-v2"
    inference = ROOT / "evals/e2b-regression-v2-inference"
    metadata = {row["task_id"]: row for row in _rows(corpus / "metadata.jsonl")}
    e2b = {row["task_id"]: row for row in _rows(inference / "e2b.jsonl")}
    assessments = {row["task_id"]: row["assessment"] for row in _rows(inference / "functiongemma.jsonl")}
    all_rows: list[dict[str, Any]] = []
    for split in SPLITS:
        inputs = {row["task_id"]: row for row in _rows(corpus / "inputs" / f"{split}.jsonl")}
        ref_dir = "sealed" if split == "final_holdout" else "references"
        refs = {row["task_id"]: row for row in _rows(corpus / ref_dir / f"{split}.jsonl")}
        if set(inputs) != set(refs) or not set(inputs) <= set(e2b):
            raise ValueError(f"Input/reference/candidate mismatch for {split}.")
        for task_id, task in inputs.items():
            raw = str(e2b[task_id]["answer"])
            envelope = TaskEnvelope(id=task_id, input_text=str(task["prompt"]))
            contract = apply_answer_contract(envelope, raw)
            normalized = contract.answer if contract.valid else raw.strip()
            repeated = apply_answer_contract(envelope, normalized)
            idempotent = repeated.answer == normalized and repeated.valid == contract.valid
            effective_contract_valid = contract.valid and idempotent
            if not idempotent:
                normalized = raw.strip()
            contract_payload = contract.to_dict()
            contract_payload["effective_valid"] = effective_contract_valid
            if not idempotent:
                contract_payload["effective_reason"] = "non_idempotent_contract"
            local_evidence = build_local_adjudication_evidence(envelope, normalized).to_dict()
            mechanical = _mechanical(
                refs[task_id],
                normalized,
                effective_contract_valid,
                metadata[task_id]["category"],
                local_evidence=local_evidence,
            )
            row = {
                "schema_version": SCHEMA,
                "id": f"e2b-v2-{task_id}",
                "task_id": task_id,
                "split": split,
                "category": metadata[task_id]["category"],
                "task_text": task["prompt"],
                "raw_answer": raw,
                "answer": normalized,
                "reference_answer": refs[task_id]["reference_answer"],
                "reference_rubric": refs[task_id]["reference_rubric"],
                "answer_mode": refs[task_id]["answer_mode"],
                "output_shape": refs[task_id]["output_shape"],
                "answer_contract": contract_payload,
                "normalization_changed": normalized != raw.strip(),
                "contract_idempotent": idempotent,
                "mechanical": mechanical,
                "local_verifier_evidence": local_evidence,
                "functiongemma_assessment": assessments.get(task_id),
                "assessment_valid": task_id in assessments,
                "generator_provider": metadata[task_id]["generator_provider"],
                "eligible_judges": metadata[task_id]["eligible_judges"],
                "engine": "gemma4-e2b",
                "engine_version": "gemma-4-E2B-it-litert-lm-6664aee5",
            }
            all_rows.append(row)
    development = [row for row in all_rows if row["split"] != "final_holdout"]
    final = [row for row in all_rows if row["split"] == "final_holdout"]
    _write_jsonl(output / "development" / "candidates.jsonl", development)
    _write_jsonl(output / "sealed" / "final-holdout-candidates.jsonl", final)
    _write_jsonl(output / "development" / "judge-queue.jsonl", [row for row in development if row["mechanical"]["verdict"] == "uncertain"])
    _write_jsonl(output / "sealed" / "final-holdout-judge-queue.jsonl", [row for row in final if row["mechanical"]["verdict"] == "uncertain"])
    summary = _prepare_summary(all_rows)
    _write_json(output / "prepare-summary.json", summary)
    return summary


def consolidate(output: Path) -> dict[str, Any]:
    development = _rows(output / "development" / "candidates.jsonl")
    final = _rows(output / "sealed" / "final-holdout-candidates.jsonl")
    judgments = _judgment_index(
        _rows(output / "judgments" / "fireworks.jsonl")
        + _rows(output / "judgments" / "agy.jsonl")
        + _rows(output / "judgments" / "adjudicator.jsonl")
    )
    final_judgments = _judgment_index(
        _rows(output / "sealed" / "judgments-fireworks.jsonl")
        + _rows(output / "sealed" / "judgments-agy.jsonl")
        + _rows(output / "sealed" / "judgments-adjudicator.jsonl")
    )
    _write_jsonl(
        output / "judgments" / "adjudication-queue.jsonl",
        _disagreement_queue(development, judgments),
    )
    _write_jsonl(
        output / "sealed" / "adjudication-queue.jsonl",
        _disagreement_queue(final, final_judgments),
    )
    development_labels = [_label(row, judgments.get(row["id"], [])) for row in development]
    final_labels = [_label(row, final_judgments.get(row["id"], [])) for row in final]
    _write_jsonl(output / "development" / "labels.jsonl", development_labels)
    _write_jsonl(output / "sealed" / "final-holdout-labels.jsonl", final_labels)
    summary = _label_summary(development_labels, final_labels)
    policy = {
        "schema_version": "e2b-regression-v2-label-policy-v1",
        "correct_to_binary": 1,
        "incorrect_to_binary": 0,
        "uncertain_to_binary": 0,
        "mechanical_precedence": True,
        "judge_consensus_required": 2,
        "third_judge_on_pair_disagreement": True,
        "generator_may_not_be_sole_judge": True,
        "invalid_assessment_route": "fireworks",
        "development_labels_sha256": _sha256(output / "development" / "labels.jsonl"),
        "sealed_final_labels_sha256": _sha256(output / "sealed" / "final-holdout-labels.jsonl"),
        "development_candidates_sha256": _sha256(output / "development" / "candidates.jsonl"),
        "sealed_final_candidates_sha256": _sha256(output / "sealed" / "final-holdout-candidates.jsonl"),
        "judge_ledgers_sha256": {
            "development_fireworks": _sha256(output / "judgments" / "fireworks.jsonl"),
            "development_agy": _sha256(output / "judgments" / "agy.jsonl"),
            "development_adjudicator": _sha256(output / "judgments" / "adjudicator.jsonl"),
            "sealed_fireworks": _sha256(output / "sealed" / "judgments-fireworks.jsonl"),
            "sealed_agy": _sha256(output / "sealed" / "judgments-agy.jsonl"),
            "sealed_adjudicator": _sha256(output / "sealed" / "judgments-adjudicator.jsonl"),
        },
        "default_enabled": False,
    }
    _write_json(ROOT / "configs/e2b-regression-v2-label-policy.json", policy)
    _write_report(ROOT / "reports/generated/e2b-regression-v2-adjudication.md", summary)
    return summary


def check(output: Path) -> dict[str, Any]:
    policy_path = ROOT / "configs/e2b-regression-v2-label-policy.json"
    policy = json.loads(policy_path.read_text())
    development = _rows(output / "development" / "labels.jsonl")
    final = _rows(output / "sealed" / "final-holdout-labels.jsonl")
    all_rows = development + final
    adjudicated = [row for row in all_rows if len(row["judge_verdicts"]) >= 3]
    adjudication_resolution = (
        sum(_majority_verdict(row["judge_verdicts"]) is not None for row in adjudicated) / len(adjudicated)
        if adjudicated
        else 0.0
    )
    judge_paths = {
        "development_fireworks": output / "judgments" / "fireworks.jsonl",
        "development_agy": output / "judgments" / "agy.jsonl",
        "development_adjudicator": output / "judgments" / "adjudicator.jsonl",
        "sealed_fireworks": output / "sealed" / "judgments-fireworks.jsonl",
        "sealed_agy": output / "sealed" / "judgments-agy.jsonl",
        "sealed_adjudicator": output / "sealed" / "judgments-adjudicator.jsonl",
    }
    gates = {
        "development_rows": len(development) == 1600,
        "sealed_final_rows": len(final) == 400,
        "unique_ids": len({row["task_id"] for row in development + final}) == 2000,
        "no_semantic_contract_repairs": all(not row["normalization_changed"] or row["contract_idempotent"] for row in development + final),
        "no_invalid_mechanical_correct": all(not (row["final_label"] == "correct" and row["mechanical_verdict"] == "incorrect") for row in development + final),
        "traceable": all(row["evidence_source"] in {"mechanical", "judge_consensus", "judge_adjudication", "judge_disagreement", "missing_judges"} for row in development + final),
        "development_hash": _sha256(output / "development" / "labels.jsonl") == policy["development_labels_sha256"],
        "sealed_hash": _sha256(output / "sealed" / "final-holdout-labels.jsonl") == policy["sealed_final_labels_sha256"],
        "development_candidates_hash": _sha256(output / "development" / "candidates.jsonl") == policy["development_candidates_sha256"],
        "sealed_candidates_hash": _sha256(output / "sealed" / "final-holdout-candidates.jsonl") == policy["sealed_final_candidates_sha256"],
        "judge_ledger_hashes": all(
            _sha256(path) == policy["judge_ledgers_sha256"].get(name)
            for name, path in judge_paths.items()
        ),
        "fit_firewall": policy.get("default_enabled") is False,
        "invalid_assessment_remote_fallback": policy.get("invalid_assessment_route") == "fireworks",
        "adjudication_resolution_at_least_95pct": adjudication_resolution >= 0.95,
        "all_pair_disagreements_adjudicated": all(
            row["evidence_source"] != "judge_disagreement" or len(row["judge_verdicts"]) >= 3
            for row in all_rows
        ),
        "independent_judge_quorum": all(
            row["evidence_source"] == "mechanical" or len(set(row["judge_models"])) >= 2
            for row in all_rows
        ),
    }
    if not all(gates.values()):
        raise ValueError(f"Adjudication gates failed: {[k for k,v in gates.items() if not v]}")
    return {"passed": True, "gates": gates, "development": len(development), "sealed_final": len(final)}


def _mechanical(
    reference: Mapping[str, Any],
    answer: str,
    contract_valid: bool,
    category: str,
    *,
    local_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not contract_valid:
        return {"verdict": "incorrect", "hard": True, "reason": "contract_invalid"}
    if local_evidence and local_evidence.get("hard_gate_passed") is True:
        family = str(local_evidence.get("verifier_family") or "registered")
        return {"verdict": "correct", "hard": True, "reason": f"verified:{family}"}
    expected = str(reference["reference_answer"])
    shape = reference["output_shape"]
    if shape == "number":
        try:
            equal = float(answer.replace(",", "")) == float(expected.replace(",", ""))
        except ValueError:
            return {"verdict": "incorrect", "hard": True, "reason": "invalid_number"}
        return {"verdict": "correct" if equal else "incorrect", "hard": True, "reason": "numeric_equality"}
    if shape == "label":
        equal = _norm(answer) == _norm(expected)
        return {"verdict": "correct" if equal else "incorrect", "hard": True, "reason": "label_equality"}
    if shape == "json":
        try:
            equal = _json_norm(json.loads(answer)) == _json_norm(json.loads(expected))
        except (json.JSONDecodeError, TypeError):
            return {"verdict": "incorrect", "hard": True, "reason": "invalid_json"}
        return {"verdict": "correct" if equal else "incorrect", "hard": True, "reason": "json_equality"}
    if _norm(answer) == _norm(expected):
        return {"verdict": "correct", "hard": True, "reason": "exact_reference_match"}
    return {"verdict": "uncertain", "hard": False, "reason": f"semantic_{category}_requires_judge"}


def _label(row: Mapping[str, Any], judgments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    mechanical = row["mechanical"]
    verdicts = [str(j["verdict"]) for j in judgments]
    if mechanical["hard"]:
        label, source = mechanical["verdict"], "mechanical"
    elif len(verdicts) >= 2 and _majority_verdict(verdicts) is not None:
        label = _majority_verdict(verdicts)
        source = "judge_consensus" if len(verdicts) == 2 else "judge_adjudication"
    elif len(verdicts) >= 2:
        label, source = "uncertain", "judge_disagreement"
    else:
        label, source = "uncertain", "missing_judges"
    return {
        "schema_version": SCHEMA,
        "task_id": row["task_id"],
        "split": row["split"],
        "category": row["category"],
        "final_label": label,
        "binary_label": int(label == "correct"),
        "evidence_source": source,
        "mechanical_verdict": mechanical["verdict"],
        "contract_valid": row["answer_contract"].get("effective_valid", row["answer_contract"]["valid"]),
        "normalization_changed": row["normalization_changed"],
        "contract_idempotent": row["contract_idempotent"],
        "assessment_valid": row["assessment_valid"],
        "functiongemma_assessment": row["functiongemma_assessment"],
        "judge_verdicts": verdicts,
        "judge_models": [j["judge_model"] for j in judgments],
        "candidate_sha256": hashlib.sha256(row["answer"].encode()).hexdigest(),
    }


def _judgment_index(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row["candidate_id"]), str(row["judge_model"]))
        if key in seen:
            continue
        seen.add(key)
        result.setdefault(key[0], []).append(dict(row))
    return result


def _majority_verdict(verdicts: Sequence[str]) -> str | None:
    counts = Counter(verdicts)
    verdict, count = counts.most_common(1)[0]
    return verdict if count >= 2 else None


def _disagreement_queue(
    candidates: Sequence[Mapping[str, Any]],
    judgments: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for row in candidates:
        if row["mechanical"]["hard"]:
            continue
        existing = judgments.get(str(row["id"]), ())
        verdicts = [str(item["verdict"]) for item in existing]
        if len(verdicts) == 2 and len(set(verdicts)) > 1:
            queue.append(dict(row))
    return queue


def _prepare_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = Counter(row["mechanical"]["verdict"] for row in rows)
    return {"rows": len(rows), "development": sum(row["split"] != "final_holdout" for row in rows), "sealed_final": sum(row["split"] == "final_holdout" for row in rows), "contract_changed": sum(row["normalization_changed"] for row in rows), "contract_invalid": sum(not row["answer_contract"].get("effective_valid", row["answer_contract"]["valid"]) for row in rows), "non_idempotent_quarantined": sum(not row["contract_idempotent"] for row in rows), "idempotent": sum(row["contract_idempotent"] for row in rows), "mechanical": dict(sorted(counts.items())), "judge_queue": counts["uncertain"]}


def _label_summary(development: Sequence[Mapping[str, Any]], final: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    def counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]: return dict(sorted(Counter(row["final_label"] for row in rows).items()))
    consensus = [row for row in development + final if len(row["judge_verdicts"]) >= 2]
    agreed = sum(len(set(row["judge_verdicts"][:2])) == 1 for row in consensus)
    adjudicated = [row for row in development + final if len(row["judge_verdicts"]) >= 3]
    resolved = sum(_majority_verdict(row["judge_verdicts"]) is not None for row in adjudicated)
    all_rows = list(development) + list(final)
    categories = {
        category: {
            "rows": len(rows),
            "correct": sum(row["final_label"] == "correct" for row in rows),
            "incorrect": sum(row["final_label"] == "incorrect" for row in rows),
            "uncertain": sum(row["final_label"] == "uncertain" for row in rows),
        }
        for category in sorted({str(row["category"]) for row in all_rows})
        if (rows := [row for row in all_rows if row["category"] == category])
    }
    return {"development_rows": len(development), "sealed_final_rows": len(final), "development_labels": counts(development), "sealed_final_labels": counts(final), "judge_pairs": len(consensus), "judge_agreement_rate": agreed / len(consensus) if consensus else 0.0, "adjudicated_disagreements": len(adjudicated), "adjudication_resolution_rate": resolved / len(adjudicated) if adjudicated else 0.0, "format_recoveries": sum(row["normalization_changed"] and row["final_label"] == "correct" for row in all_rows), "assessment_invalid_remote_fallback": sum(not row["assessment_valid"] for row in all_rows), "evidence_sources": dict(sorted(Counter(row["evidence_source"] for row in all_rows).items())), "categories": categories}


def _json_norm(value: Any) -> Any:
    if isinstance(value, Mapping): return {str(k): _json_norm(v) for k,v in sorted(value.items())}
    if isinstance(value, list): return [_json_norm(v) for v in value]
    if isinstance(value, str): return _norm(value)
    return value


def _norm(value: str) -> str: return " ".join(re.sub(r"[^\w.+-]+", " ", value.casefold()).split())
def _rows(path: Path) -> list[dict[str, Any]]: return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []
def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None: path.parent.mkdir(parents=True,exist_ok=True); path.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n" for r in rows))
def _write_json(path: Path, value: Mapping[str, Any]) -> None: path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")
def _sha256(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def _absolute(path: Path) -> Path: return path if path.is_absolute() else ROOT/path
def _write_report(path: Path, summary: Mapping[str, Any]) -> None: path.parent.mkdir(parents=True,exist_ok=True); path.write_text("# E2B Regression V2 Adjudication\n\n"+"\n".join(f"- {k}: `{v}`" for k,v in sorted(summary.items()))+"\n")


if __name__ == "__main__":
    raise SystemExit(main())
