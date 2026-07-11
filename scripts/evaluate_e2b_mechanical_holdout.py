#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import FeatureVector, TaskAssessment, TaskEnvelope
from router.orchestration.assessment import build_feature_vector, compute_structural_features
from router.orchestration.e2b_selective_gate import E2BSelectivePolicy
from scripts.promote_e2b_policy import _wilson_lower


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mechanically score a fresh E2B selective-routing holdout.")
    parser.add_argument("--tasks", type=Path, default=Path("data/e2b-selective-holdout/tasks.jsonl"))
    parser.add_argument("--assessments", type=Path, required=True)
    parser.add_argument("--e2b-candidates", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("configs/e2b-selective-policy-v1.json"))
    parser.add_argument("--policy-sha256")
    parser.add_argument("--kimi-candidates", type=Path)
    parser.add_argument("--report", type=Path, default=Path("reports/generated/e2b-selective-fresh-holdout.json"))
    args = parser.parse_args(argv)
    report = evaluate_holdout(
        tasks_path=_absolute(args.tasks),
        assessments_path=_absolute(args.assessments),
        e2b_candidates_path=_absolute(args.e2b_candidates),
        policy_path=_absolute(args.policy),
        policy_sha256=args.policy_sha256,
        kimi_candidates_path=_absolute(args.kimi_candidates) if args.kimi_candidates else None,
    )
    output = _absolute(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


def evaluate_holdout(
    *,
    tasks_path: Path,
    assessments_path: Path,
    e2b_candidates_path: Path,
    policy_path: Path,
    policy_sha256: str | None = None,
    kimi_candidates_path: Path | None = None,
) -> dict[str, Any]:
    tasks = {str(row["id"]): row for row in _jsonl(tasks_path)}
    assessments = {
        str(row["id"]): row.get("prediction")
        for row in _jsonl(assessments_path)
        if isinstance(row.get("prediction"), Mapping)
    }
    e2b = {str(row["task_id"]): row for row in _jsonl(e2b_candidates_path)}
    if set(tasks) != set(assessments) or set(tasks) != set(e2b):
        raise ValueError("Tasks, FunctionGemma assessments and E2B candidates must have identical IDs.")
    kimi = {str(row["task_id"]): row for row in _jsonl(kimi_candidates_path)} if kimi_candidates_path else {}
    if kimi and set(kimi) != set(tasks):
        raise ValueError("Kimi candidates must cover the complete holdout.")
    policy = E2BSelectivePolicy.load(policy_path, expected_sha256=policy_sha256)
    rows: list[dict[str, Any]] = []
    for task_id, task_row in tasks.items():
        task = TaskEnvelope(id=task_id, input_text=str(task_row["input_text"]))
        assessment = TaskAssessment.from_mapping(assessments[task_id])
        features = build_feature_vector(assessment, compute_structural_features(task))
        candidate = e2b[task_id]
        e2b_correct, e2b_reason = score_answer(task_row["evaluation"], str(candidate.get("answer") or ""))
        decision = policy.evaluate(task, str(candidate.get("answer") or ""), features)
        kimi_correct: bool | None = None
        kimi_tokens = 0
        if kimi:
            kimi_candidate = kimi[task_id]
            kimi_correct, _ = score_answer(task_row["evaluation"], str(kimi_candidate.get("answer") or ""))
            usage = kimi_candidate.get("fireworks_tokens") or {}
            kimi_tokens = int(usage.get("prompt") or 0) + int(usage.get("completion") or 0)
        rows.append(
            {
                "task_id": task_id,
                "intent": assessment.intent.value,
                "probe": decision.probe,
                "accepted": decision.accepted,
                "pre_probability": decision.pre_probability,
                "post_probability": decision.post_probability,
                "decision_reason": decision.reason,
                "e2b_correct": e2b_correct,
                "e2b_score_reason": e2b_reason,
                "kimi_correct": kimi_correct,
                "kimi_tokens": kimi_tokens,
            }
        )
    selected = [row for row in rows if row["accepted"]]
    local_correct = sum(row["e2b_correct"] is True for row in selected)
    summary: dict[str, Any] = {
        "rows": len(rows),
        "probed": sum(row["probe"] for row in rows),
        "selected": len(selected),
        "coverage": len(selected) / len(rows),
        "local_correct": local_correct,
        "local_accuracy": local_correct / len(selected) if selected else 0.0,
        "local_wilson_lower_95": _wilson_lower(local_correct, len(selected)),
        "selected_by_intent": dict(sorted(Counter(row["intent"] for row in selected).items())),
        "policy_enabled": policy.enabled,
        "policy_sha256": policy.artifact_sha256,
    }
    if kimi:
        kimi_correct = sum(row["kimi_correct"] is True for row in rows)
        hybrid_correct = sum(
            (row["e2b_correct"] if row["accepted"] else row["kimi_correct"]) is True
            for row in rows
        )
        summary.update(
            {
                "kimi_correct": kimi_correct,
                "hybrid_correct": hybrid_correct,
                "hybrid_accuracy_delta": (hybrid_correct - kimi_correct) / len(rows),
                "saved_fireworks_tokens": sum(row["kimi_tokens"] for row in selected),
                "hybrid_noninferior_exact": hybrid_correct >= kimi_correct,
            }
        )
    return {
        "schema_version": "e2b-selective-fresh-holdout-report-v1",
        "summary": summary,
        "rows": rows,
    }


def score_answer(evaluation: Mapping[str, Any], answer: str) -> tuple[bool, str]:
    kind = evaluation.get("type")
    expected = evaluation.get("expected")
    normalized = _strip_fence(answer)
    if kind == "label":
        correct = normalized.casefold().strip(" .\"'") == str(expected).casefold()
        return correct, "exact_label" if correct else "label_mismatch"
    if kind == "exact":
        correct = _normalize_text(normalized) == _normalize_text(str(expected))
        return correct, "exact_text" if correct else "text_mismatch"
    if kind == "json_object":
        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError:
            return False, "invalid_json"
        if not isinstance(payload, Mapping) or not isinstance(expected, Mapping):
            return False, "json_shape_mismatch"
        actual = {str(key): _normalize_text(str(value)) for key, value in payload.items()}
        gold = {str(key): _normalize_text(str(value)) for key, value in expected.items()}
        correct = actual == gold
        return correct, "exact_json_object" if correct else "json_value_mismatch"
    raise ValueError(f"Unsupported mechanical evaluator {kind!r}.")


def _strip_fence(value: str) -> str:
    stripped = value.strip()
    stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().strip("\"'").casefold().split())


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
