#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import AssessmentScores, Intent, SUB_INTENTS_BY_INTENT, TaskAssessment
from router.functiongemma.tooling import training_conversation, validate_training_row, write_jsonl
from scripts.relabel_semantic_teachers import _prompt_index


def main() -> int:
    parser = argparse.ArgumentParser(description="Build FunctionGemma SFT splits from teacher consensus.")
    parser.add_argument(
        "--teacher-root", type=Path, default=Path("reports/generated/semantic-teacher-relabel-v1"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/generated/functiongemma-teacher-consensus-v3"),
    )
    parser.add_argument("--minimum-confidence", type=int, default=70)
    args = parser.parse_args()
    teacher_root = _absolute(args.teacher_root)
    output = _absolute(args.output)
    ledger = _keyed(_rows(ROOT / "reports/generated/e2b-expansion-v1/regression-ledger.jsonl"), "task_id")
    prompts = _prompt_index()
    agy = _teacher_items(teacher_root / "agy-batches.jsonl")
    codex_path = teacher_root / "codex-fill-batches.jsonl"
    codex_fill = _teacher_items(codex_path) if codex_path.is_file() else {}
    semantic_primary = {**codex_fill, **agy}
    teachers = {
        "agy_plus_codex_fill": semantic_primary,
        "kimi": _teacher_items(teacher_root / "kimi-batches.jsonl"),
    }

    splits: dict[str, list[dict[str, Any]]] = {"train": [], "validation": []}
    disagreements = Counter()
    score_deltas: dict[str, list[int]] = {
        name: [] for name in (
            "difficulty", "reasoning_demand", "generation_demand", "knowledge_requirement",
            "ambiguity", "deterministic_fit",
        )
    }
    for task_id, row in ledger.items():
        split = {"fit": "train", "calibration": "validation"}.get(str(row["role"]))
        if split is None:
            continue
        left = teachers["agy_plus_codex_fill"].get(task_id)
        right = teachers["kimi"].get(task_id)
        if left is None or right is None:
            disagreements["missing_teacher"] += 1
            continue
        if min(int(left["confidence"]), int(right["confidence"])) < args.minimum_confidence:
            disagreements["low_confidence"] += 1
            continue
        if left["intent"] != right["intent"]:
            disagreements["intent_disagreement"] += 1
            continue
        for name in score_deltas:
            score_deltas[name].append(abs(int(left[name]) - int(right[name])))
        assessment = _consensus(left, right, row["mechanical_features"])
        conversation = training_conversation(prompts[task_id], assessment)
        prepared = {
            "id": task_id,
            "mutation_lineage": row["mutation_lineage"],
            "template_family": row.get("template_family"),
            "source": row["source"],
            "teacher_consensus": {
                "providers": [
                    "agy" if task_id in agy else "codex-fill",
                    "fireworks:kimi-k2p7-code",
                ],
                "intent": assessment.intent.value,
                "minimum_confidence": min(int(left["confidence"]), int(right["confidence"])),
            },
            **conversation,
        }
        validate_training_row(prepared)
        splits[split].append(prepared)

    output.mkdir(parents=True, exist_ok=True)
    for split, rows in splits.items():
        rows.sort(key=lambda row: row["id"])
        write_jsonl(output / f"{split}.jsonl", rows)
    report = {
        "schema_version": "functiongemma-teacher-consensus-v3",
        "counts": {name: len(rows) for name, rows in splits.items()},
        "excluded": dict(disagreements),
        "teacher_coverage": {name: len(items) for name, items in teachers.items()},
        "primary_teacher_breakdown": {"agy": len(agy), "codex_fill": len(codex_fill)},
        "mean_absolute_teacher_delta": {
            name: statistics.fmean(values) if values else None for name, values in score_deltas.items()
        },
        "minimum_confidence": args.minimum_confidence,
        "split_policy": "ledger fit->train, calibration->validation; protected rows excluded",
        "sha256": {
            split: hashlib.sha256((output / f"{split}.jsonl").read_bytes()).hexdigest()
            for split in splits
        },
    }
    (output / "consensus-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))
    return 0


def _consensus(
    left: Mapping[str, Any], right: Mapping[str, Any], mechanical: Mapping[str, Any],
) -> TaskAssessment:
    def mean(name: str) -> float:
        weights = (max(1, int(left["confidence"])), max(1, int(right["confidence"])))
        return (float(left[name]) * weights[0] + float(right[name]) * weights[1]) / sum(weights)

    reasoning = round(0.7 * mean("reasoning_demand") + 0.3 * mean("difficulty") * 2.5)
    knowledge = round(0.8 * mean("knowledge_requirement") + 0.2 * mean("ambiguity"))
    scores = AssessmentScores(
        deterministic_fit=_bounded(round(mean("deterministic_fit"))),
        reasoning_demand=_bounded(reasoning),
        knowledge_uncertainty=_bounded(knowledge),
        generation_demand=_bounded(round(mean("generation_demand"))),
        format_complexity=_format_complexity(mechanical),
    )
    return TaskAssessment(intent=Intent(str(left["intent"])), scores=scores)


def _format_complexity(features: Mapping[str, Any]) -> int:
    score = (
        2.0 * float(features["mechanical.strict_format"])
        + 2.0 * float(features["mechanical.json_requested"])
        + 1.0 * float(features["mechanical.shape.code"])
        + 2.0 * float(features["mechanical.shape.json"])
        + 1.0 * float(float(features["mechanical.sentence_limit"]) > 0)
        + 1.0 * float(float(features["mechanical.word_limit"]) > 0)
        + 1.0 * float(features["mechanical.shape.list"])
        + 1.0 * float(features["mechanical.verifier.code_syntax"])
        + 1.0 * float(features["mechanical.verifier.json_structure"])
    )
    return _bounded(round(score))


def _teacher_items(path: Path) -> dict[str, Mapping[str, Any]]:
    result = {}
    for batch in _rows(path):
        for item in batch.get("items", []):
            if not isinstance(item, dict):
                raise ValueError(f"Malformed teacher item in {path}.")
            task_id = str(item.get("task_id") or "")
            Intent(str(item.get("intent") or ""))
            if task_id in result:
                raise ValueError(f"Duplicate teacher label for {task_id} in {path}.")
            result[task_id] = item
    return result


def _bounded(value: int) -> int:
    return max(0, min(10, value))


def _keyed(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, Mapping[str, Any]]:
    return {str(row[field]): row for row in rows}


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
