#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.orchestration.e2b_mechanical_features import extract_e2b_mechanical_features

SCHEMA = "router-ml-v3-ledger-v1"
SCORES = ("deterministic_fit", "reasoning_demand", "knowledge_uncertainty", "generation_demand", "format_complexity")
INTENTS = ("factual_qa", "math_reasoning", "sentiment", "summarization", "ner", "code_debugging", "logic_puzzle", "code_generation")


def _jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _index(path: Path) -> dict[str, dict[str, Any]]:
    rows = _jsonl(path)
    result = {str(row["task_id"]): row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"duplicate task_id in {path}")
    return result


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _contract_features(candidate: Mapping[str, Any]) -> dict[str, float]:
    contract = candidate.get("contract") or candidate.get("answer_contract") or {}
    inner = contract.get("contract", {}) if isinstance(contract, Mapping) else {}
    kind = str(inner.get("kind", "free_text"))
    return {
        "contract.valid": float(bool(contract.get("effective_valid", contract.get("valid", False)))),
        "contract.strict": float(bool(inner.get("strict", False))),
        "contract.changed": float(bool(contract.get("changed", candidate.get("normalization_changed", False)))),
        "contract.exact_items": float(inner.get("exact_items") or 0),
        "contract.exact_sentences": float(inner.get("exact_sentences") or 0),
        "contract.max_words_log": math.log1p(float(inner.get("max_words") or 0)),
        **{f"contract.kind.{name}": float(kind == name) for name in ("free_text", "label", "number", "list", "json", "code")},
    }


def _proof_features(candidate: Mapping[str, Any]) -> dict[str, float]:
    evidence = candidate.get("local_verifier_evidence", {})
    return {
        "proof.supported": float(bool(evidence.get("verifier_supported", False))),
        "proof.unique": float(bool(evidence.get("proof_unique", False))),
        "proof.valid": float(bool(evidence.get("proof_valid", False))),
        "proof.registered": float(str(evidence.get("verifier_family", "none")) != "none"),
    }


def _row(source: str, metadata: Mapping[str, Any], candidate: Mapping[str, Any], label: Mapping[str, Any] | None) -> dict[str, Any]:
    task_id = str(metadata["task_id"])
    prompt = str(candidate.get("prompt", candidate.get("task_text", "")))
    if not prompt:
        raise ValueError(f"missing prompt: {task_id}")
    assessment = candidate.get("functiongemma_assessment")
    assessment_valid = bool(candidate.get("assessment_valid")) and isinstance(assessment, Mapping)
    semantic: dict[str, float] = {}
    intent = "invalid"
    if assessment_valid:
        intent = str(assessment.get("intent", "invalid"))
        scores = assessment.get("scores", {})
        if not all(name in scores for name in SCORES):
            assessment_valid = False
            intent = "invalid"
        else:
            semantic = {f"fg.{name}": float(scores[name]) / 10.0 for name in SCORES}
    mechanical = extract_e2b_mechanical_features(prompt).to_dict()["features"]
    protected = str(metadata.get("split")) == "final_holdout"
    features = {**semantic, **{str(k): float(v) for k, v in mechanical.items()}, **_contract_features(candidate), **_proof_features(candidate)}
    features.update({f"intent.{name}": float(assessment_valid and intent == name) for name in INTENTS})
    features["assessment.missing"] = float(not assessment_valid)
    features["prompt.char_log"] = math.log1p(len(prompt))
    features["prompt.line_log"] = math.log1p(prompt.count("\n") + 1)
    features["prompt.constraint_count"] = float(len(re.findall(r"\b(?:only|exactly|must|maximum|minimum|no more than|without)\b", prompt, re.I)))
    verifier = candidate.get("local_verifier_evidence", {})
    deterministic_target = None if protected else int(bool(verifier.get("hard_gate_passed") and verifier.get("proof_valid") and verifier.get("proof_unique")))
    e2b_target = None if protected or label is None else int(label["binary_label"])
    return {
        "schema_version": SCHEMA,
        "task_id": task_id,
        "source": source,
        "role": "protected_holdout" if protected else ("calibration" if str(metadata.get("split")) in {"calibration", "validation"} else "fit"),
        "category": str(metadata["category"]),
        "difficulty": str(metadata.get("difficulty", "unknown")),
        "lineage": f"{source}:{metadata['mutation_lineage']}",
        "template_family": str(metadata.get("template_family", "unknown")),
        "prompt_sha256": str(metadata["prompt_sha256"]),
        "assessment_valid": assessment_valid,
        "intent": intent,
        "features": features,
        "targets": {"deterministic": deterministic_target, "e2b": e2b_target},
        "provenance": {
            "prompt_provider": metadata.get("provider", metadata.get("generator_provider")),
            "e2b_model": candidate.get("engine_version", candidate.get("generator_provider")),
            "label_source": None if protected or label is None else label.get("evidence_source"),
            "contract_schema": (candidate.get("contract") or candidate.get("answer_contract") or {}).get("schema_version"),
        },
    }


def build(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    specs = [
        ("expansion-v1", root / "evals/e2b-expansion-v1/metadata.jsonl", root / "evals/e2b-expansion-v1/adjudication/development/candidates.jsonl", root / "evals/e2b-expansion-v1/adjudication/development/labels.jsonl", root / "evals/e2b-expansion-v1/adjudication/sealed/candidates.jsonl"),
        ("regression-v2", root / "evals/e2b-regression-v2/metadata.jsonl", root / "evals/e2b-regression-v2-adjudication/development/candidates.jsonl", root / "evals/e2b-regression-v2-adjudication/development/labels.jsonl", root / "evals/e2b-regression-v2-adjudication/sealed/final-holdout-candidates.jsonl"),
    ]
    result: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    attrition: dict[str, int] = {}
    seen_prompts: dict[str, str] = {}
    for source, metadata_path, dev_candidates_path, dev_labels_path, protected_candidates_path in specs:
        metadata, dev_candidates, labels, protected_candidates = _index(metadata_path), _index(dev_candidates_path), _index(dev_labels_path), _index(protected_candidates_path)
        hashes.update({str(path.relative_to(root)): _sha(path) for path in (metadata_path, dev_candidates_path, dev_labels_path, protected_candidates_path)})
        candidates = {**dev_candidates, **protected_candidates}
        if set(metadata) != set(candidates):
            raise ValueError(f"candidate coverage mismatch for {source}: metadata={len(metadata)}, candidates={len(candidates)}")
        for task_id in sorted(metadata):
            row = _row(source, metadata[task_id], candidates[task_id], labels.get(task_id))
            previous = seen_prompts.get(row["prompt_sha256"])
            if previous and row["lineage"] != previous:
                attrition["duplicate_prompt_cross_lineage"] = attrition.get("duplicate_prompt_cross_lineage", 0) + 1
                continue
            seen_prompts[row["prompt_sha256"]] = row["lineage"]
            result.append(row)
    roles = {role: sum(row["role"] == role for row in result) for role in ("fit", "calibration", "protected_holdout")}
    lineages = {role: len({row["lineage"] for row in result if row["role"] == role}) for role in roles}
    overlap = {a + "_" + b: len({row["lineage"] for row in result if row["role"] == a} & {row["lineage"] for row in result if row["role"] == b}) for a, b in (("fit", "calibration"), ("fit", "protected_holdout"), ("calibration", "protected_holdout"))}
    if any(overlap.values()):
        raise ValueError(f"lineage leakage: {overlap}")
    manifest = {"schema_version": "router-ml-v3-manifest-v1", "rows": len(result), "roles": roles, "lineages": lineages, "lineage_overlap": overlap, "attrition": attrition, "source_hashes": hashes, "protected_targets_redacted": True}
    return result, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "evals/router-ml-v3/ledger.jsonl")
    parser.add_argument("--manifest", type=Path, default=ROOT / "evals/router-ml-v3/manifest.json")
    args = parser.parse_args()
    rows, manifest = build(ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    manifest["ledger_sha256"] = _sha(args.output)
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
