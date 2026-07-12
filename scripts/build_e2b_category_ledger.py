#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.orchestration.e2b_mechanical_features import extract_e2b_mechanical_features


SCORE_NAMES = (
    "deterministic_fit", "reasoning_demand", "knowledge_uncertainty",
    "generation_demand", "format_complexity",
)


def main() -> int:
    rows = [*_legacy(), *_v2(), *_boundary(), *_expansion_if_ready()]
    ids = [row["task_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Category ledger contains duplicate task IDs.")
    output = ROOT / "reports/generated/e2b-expansion-v1/regression-ledger.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    report = {
        "schema_version": "e2b-category-regression-ledger-report-v1",
        "rows": len(rows), "unique_task_ids": len(set(ids)),
        "by_source": dict(sorted(Counter(row["source"] for row in rows).items())),
        "by_role": dict(sorted(Counter(row["role"] for row in rows).items())),
        "by_category": dict(sorted(Counter(row["category"] for row in rows).items())),
        "correct": sum(row["target"] for row in rows),
        "incorrect": sum(not row["target"] for row in rows),
        "invalid_assessment": sum(not row["assessment_valid"] for row in rows),
        "fit_rows": sum(row["role"] == "fit" and row["assessment_valid"] for row in rows),
        "calibration_rows": sum(row["role"] == "calibration" and row["assessment_valid"] for row in rows),
        "protected_rows": sum(row["role"] in {"protected_holdout", "external_audit"} for row in rows),
        "ledger_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    report_path = ROOT / "reports/generated/e2b-expansion-v1/regression-ledger-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


def _legacy() -> list[dict[str, Any]]:
    tasks = _keyed(ROOT / "data/e2b-regression-2000/tasks.jsonl", "id")
    outcomes = _keyed(ROOT / "reports/generated/amd-pod-e2b-regression-2000/e2b-outcome-matrix-contract-v2.jsonl")
    assessments = _keyed(ROOT / "reports/generated/amd-pod-e2b-regression-2000/functiongemma-valid-predictions.jsonl", "id")
    rows = []
    for task_id in sorted(set(tasks) & set(outcomes) & set(assessments)):
        task, outcome = tasks[task_id], outcomes[task_id]
        split = str(task["regression_split"])
        rows.append(_row(
            task_id=task_id, source="legacy", role=_role(split), split=split,
            category=str(task["source_assessment"]["intent"]), prompt=str(task["input_text"]),
            lineage=str(task["mutation_lineage"]), template=str(task["template_family"]),
            assessment=assessments[task_id]["prediction"], target=bool(outcome["correct"]),
            contract_valid=bool(outcome.get("answer_contract_valid", True)), difficulty=None,
        ))
    return rows


def _v2() -> list[dict[str, Any]]:
    inputs = {}
    for split in ("train", "validation", "final_holdout"):
        inputs.update(_keyed(ROOT / f"evals/e2b-regression-v2/inputs/{split}.jsonl"))
    metadata = _keyed(ROOT / "evals/e2b-regression-v2/metadata.jsonl")
    labels = _keyed(ROOT / "evals/e2b-regression-v2-adjudication/development/labels.jsonl")
    labels.update(_keyed(ROOT / "evals/e2b-regression-v2-adjudication/sealed/final-holdout-labels.jsonl"))
    rows = []
    for task_id in sorted(set(inputs) & set(metadata) & set(labels)):
        label, meta = labels[task_id], metadata[task_id]
        assessment = label.get("functiongemma_assessment")
        if not isinstance(assessment, Mapping):
            continue
        split = str(meta["split"])
        rows.append(_row(
            task_id=task_id, source="v2", role=_role(split), split=split,
            category=str(meta["category"]), prompt=str(inputs[task_id]["prompt"]),
            lineage=str(meta["mutation_lineage"]), template=str(meta["template_family"]),
            assessment=assessment, target=bool(label["binary_label"]),
            contract_valid=bool(label["contract_valid"]), difficulty=None,
        ))
    return rows


def _boundary() -> list[dict[str, Any]]:
    tasks = _keyed(ROOT / "evals/e2b-boundary-v1/sealed/tasks.jsonl")
    predictions = _keyed(ROOT / "reports/generated/e2b-boundary-v1/predictions.jsonl")
    rows = []
    for task_id in sorted(set(tasks) & set(predictions)):
        task, prediction = tasks[task_id], predictions[task_id]
        assessment_envelope = prediction.get("assessment")
        if not isinstance(assessment_envelope, Mapping):
            continue
        assessment = assessment_envelope.get("raw_assessment")
        if not isinstance(assessment, Mapping):
            continue
        rows.append(_row(
            task_id=task_id, source="boundary", role="external_audit", split="sealed_boundary",
            category=str(task["category"]), prompt=str(task["prompt"]),
            lineage=str(task["mutation_lineage"]), template=str(task["mutation_lineage"]),
            assessment=assessment, target=bool(prediction["correct"]),
            contract_valid=bool(prediction.get("contract", {}).get("valid")), difficulty=None,
        ))
    return rows


def _expansion_if_ready() -> list[dict[str, Any]]:
    base = ROOT / "reports/generated/e2b-expansion-v1"
    required = (base / "functiongemma.jsonl", base / "labels.jsonl")
    if not all(path.is_file() for path in required):
        return []
    assessments = _keyed(required[0])
    labels = _keyed(required[1])
    metadata = _keyed(ROOT / "evals/e2b-expansion-v1/metadata.jsonl")
    tasks = {}
    for split in ("train", "calibration", "final_holdout"):
        path = ROOT / (f"evals/e2b-expansion-v1/sealed/tasks/{split}.jsonl" if split == "final_holdout" else f"evals/e2b-expansion-v1/splits/{split}.jsonl")
        tasks.update(_keyed(path))
    rows = []
    for task_id in sorted(set(assessments) & set(labels) & set(metadata) & set(tasks)):
        assessment = assessments[task_id].get("assessment")
        if not isinstance(assessment, Mapping):
            continue
        meta, label = metadata[task_id], labels[task_id]
        rows.append(_row(
            task_id=task_id, source="expansion", role=_role(str(meta["split"])), split=str(meta["split"]),
            category=str(meta["category"]), prompt=str(tasks[task_id]["prompt"]),
            lineage=str(meta["mutation_lineage"]), template=str(meta["template_family"]),
            assessment=assessment, target=bool(label["binary_label"]),
            contract_valid=bool(label["contract_valid"]), difficulty=str(meta["difficulty"]),
            generator_provider=str(meta["provider"]),
        ))
    return rows


def _row(
    *, task_id: str, source: str, role: str, split: str, category: str, prompt: str,
    lineage: str, template: str, assessment: Mapping[str, Any], target: bool,
    contract_valid: bool, difficulty: str | None, generator_provider: str | None = None,
) -> dict[str, Any]:
    scores = assessment.get("scores")
    if not isinstance(scores, Mapping) or any(name not in scores for name in SCORE_NAMES):
        raise ValueError(f"Invalid assessment scores for {task_id}.")
    mechanical = extract_e2b_mechanical_features(prompt).to_dict()
    return {
        "schema_version": "e2b-category-regression-ledger-v1", "task_id": task_id,
        "source": source, "role": role, "split": split, "category": category,
        "difficulty": difficulty, "generator_provider": generator_provider,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "mutation_lineage": lineage, "template_family": template,
        "assessment_valid": True, "predicted_intent": str(assessment["intent"]),
        "scores": {name: int(scores[name]) for name in SCORE_NAMES},
        "mechanical_features": mechanical["features"],
        "mechanical_schema_version": mechanical["schema_version"],
        "contract_valid": contract_valid, "target": int(target),
    }


def _role(split: str) -> str:
    if split == "train":
        return "fit"
    if split in {"validation", "calibration"}:
        return "calibration"
    return "protected_holdout"


def _keyed(path: Path, key: str = "task_id") -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            result[str(row[key])] = row
    return result


if __name__ == "__main__":
    raise SystemExit(main())
