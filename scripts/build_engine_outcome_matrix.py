#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from router.core.contracts import Engine, TaskAssessment, TaskEnvelope
from router.functiongemma.calibration import load_calibration
from router.functiongemma.tooling import file_sha256, jsonl_rows, write_jsonl
from router.orchestration.assessment import build_feature_vector, compute_structural_features


SCHEMA_VERSION = "engine-outcome-matrix-row-v1"
CONSENSUS = {
    "unanimous_correct",
    "unanimous_incorrect",
    "disagree",
    "insufficient_judges",
    "not_judged",
    "refused",
    "runtime_failure",
    "unavailable",
}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Build a long-format task x engine outcome matrix.")
    root.add_argument("--tasks", type=Path, required=True)
    root.add_argument("--assessments", type=Path, required=True)
    root.add_argument("--calibration", type=Path, required=True)
    root.add_argument("--judge-policy", type=Path, required=True)
    root.add_argument("--competition-snapshot", type=Path, required=True)
    root.add_argument("--candidate", action="append", type=Path, required=True)
    root.add_argument("--judgments", action="append", type=Path, required=True)
    root.add_argument("--unavailable-model", action="append", default=[])
    root.add_argument("--output", type=Path, required=True)
    root.add_argument("--report", type=Path, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    result = build_matrix(
        tasks_path=args.tasks,
        assessments_path=args.assessments,
        calibration_path=args.calibration,
        judge_policy_path=args.judge_policy,
        competition_snapshot_path=args.competition_snapshot,
        candidate_paths=args.candidate,
        judgment_paths=args.judgments,
        unavailable_models=args.unavailable_model,
        output=args.output,
        report_path=args.report,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def build_matrix(
    *,
    tasks_path: Path,
    assessments_path: Path,
    calibration_path: Path,
    judge_policy_path: Path,
    competition_snapshot_path: Path,
    candidate_paths: Sequence[Path],
    judgment_paths: Sequence[Path],
    unavailable_models: Sequence[str],
    output: Path,
    report_path: Path,
) -> dict[str, Any]:
    tasks = jsonl_rows(tasks_path)
    calibration = load_calibration(calibration_path)
    assessments = _assessment_index(assessments_path, calibration)
    judge_policy = _load_judge_policy(judge_policy_path)
    judgments = _judgment_index(judgment_paths)
    task_by_id = {str(row["id"]): row for row in tasks}
    if set(assessments) != set(task_by_id):
        raise ValueError("FunctionGemma assessments must cover exactly the matrix tasks.")
    matrix: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None, int]] = set()
    for path in candidate_paths:
        for candidate in jsonl_rows(path):
            task_id = str(candidate["task_id"])
            task = task_by_id.get(task_id)
            if task is None:
                raise ValueError(f"Candidate references unknown task {task_id!r}.")
            key = (
                task_id,
                str(candidate["engine"]),
                _optional_string(candidate.get("model_id")),
                int(candidate.get("generation_limit_tokens") or 0),
            )
            if key in seen:
                raise ValueError(f"Duplicate matrix observation key: {key!r}.")
            seen.add(key)
            matrix.append(
                _candidate_matrix_row(task, candidate, judgments, assessments[task_id], judge_policy)
            )
    for task in tasks:
        for model in unavailable_models:
            key = (str(task["id"]), Engine.FIREWORKS.value, model, 0)
            if key in seen:
                continue
            seen.add(key)
            matrix.append(_unavailable_row(task, model, assessments[str(task["id"])]))
    matrix.sort(key=lambda row: (row["task_id"], row["engine"], row.get("model_id") or "", row["token_ceiling"]))
    for row in matrix:
        validate_matrix_row(row)
    write_jsonl(output, matrix)
    report = _report(
        matrix,
        tasks_path=tasks_path,
        assessments_path=assessments_path,
        calibration_path=calibration_path,
        judge_policy_path=judge_policy_path,
        competition_snapshot_path=competition_snapshot_path,
        candidate_paths=candidate_paths,
        judgment_paths=judgment_paths,
        output=output,
    )
    write_json(report_path, report)
    return report


def _candidate_matrix_row(
    task: Mapping[str, Any],
    candidate: Mapping[str, Any],
    judgments: Mapping[str, list[Mapping[str, Any]]],
    assessment: TaskAssessment,
    judge_policy: Mapping[str, tuple[str, ...]],
) -> dict[str, Any]:
    status = str(candidate.get("status") or ("runtime_failure" if candidate.get("failure") else "answered"))
    if candidate.get("refusal"):
        status = "refused"
    candidate_id = str(candidate["id"])
    if status == "answered":
        policy_key = str(candidate.get("model_id") or candidate["engine"])
        allowed_judges = judge_policy.get(policy_key)
        if allowed_judges is None:
            raise ValueError(f"Judge policy is missing answered engine/model {policy_key!r}.")
        correct, consensus, judge_models, format_valid = _consensus(
            judgments.get(candidate_id, []),
            allowed_judges=allowed_judges,
        )
    elif status == "refused":
        correct, consensus, judge_models, format_valid = None, "refused", [], None
    else:
        correct, consensus, judge_models, format_valid = None, "runtime_failure", [], None
    task_text = _task_text(task)
    features = build_feature_vector(
        assessment,
        compute_structural_features(TaskEnvelope(id=str(task["id"]), input_text=task_text)),
    )
    fireworks_tokens = candidate.get("fireworks_tokens")
    prompt_tokens = _token(fireworks_tokens, "prompt")
    completion_tokens = _token(fireworks_tokens, "completion")
    engine = str(candidate["engine"])
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": str(task["id"]),
        "candidate_id": candidate_id,
        "engine": engine,
        "engine_version": str(candidate["engine_version"]),
        "model_id": _optional_string(candidate.get("model_id")),
        "status": status,
        "correct": correct,
        "consensus": consensus,
        "judge_models": judge_models,
        "format_valid": format_valid,
        "latency_ms": float(candidate.get("latency_ms") or 0.0),
        "fireworks_prompt_tokens": prompt_tokens,
        "fireworks_completion_tokens": completion_tokens,
        "runtime_failure": status == "runtime_failure",
        "peak_memory_mb": _peak_memory(engine),
        "memory_observed": engine == Engine.GEMMA_E2B.value,
        "token_ceiling": int(candidate.get("generation_limit_tokens") or 0),
        "assessment": assessment.to_dict(),
        "features": features.to_dict(),
        "regression_split": _regression_split(task.get("regression_split")),
        "mutation_lineage": _optional_string(task.get("mutation_lineage")),
        "source": _optional_string(task.get("source")),
        "missing_reason": None if correct is not None else consensus,
    }


def _unavailable_row(task: Mapping[str, Any], model: str, assessment: TaskAssessment) -> dict[str, Any]:
    task_text = _task_text(task)
    features = build_feature_vector(
        assessment,
        compute_structural_features(TaskEnvelope(id=str(task["id"]), input_text=task_text)),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": str(task["id"]),
        "candidate_id": None,
        "engine": Engine.FIREWORKS.value,
        "engine_version": "fireworks-unavailable-v1",
        "model_id": model,
        "status": "unavailable",
        "correct": None,
        "consensus": "unavailable",
        "judge_models": [],
        "format_valid": None,
        "latency_ms": 0.0,
        "fireworks_prompt_tokens": 0,
        "fireworks_completion_tokens": 0,
        "runtime_failure": True,
        "peak_memory_mb": 0.0,
        "memory_observed": True,
        "token_ceiling": 0,
        "assessment": assessment.to_dict(),
        "features": features.to_dict(),
        "regression_split": _regression_split(task.get("regression_split")),
        "mutation_lineage": _optional_string(task.get("mutation_lineage")),
        "source": _optional_string(task.get("source")),
        "missing_reason": "model_unavailable_without_dedicated_deployment",
    }


def validate_matrix_row(row: Mapping[str, Any]) -> None:
    expected = {
        "schema_version", "task_id", "candidate_id", "engine", "engine_version", "model_id", "status",
        "correct", "consensus", "judge_models", "format_valid", "latency_ms", "fireworks_prompt_tokens",
        "fireworks_completion_tokens", "runtime_failure", "peak_memory_mb", "memory_observed", "token_ceiling",
        "assessment", "features", "regression_split", "mutation_lineage", "source", "missing_reason",
    }
    if set(row) != expected or row.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Matrix row fields do not match the schema.")
    if row.get("engine") not in {engine.value for engine in Engine}:
        raise ValueError("Matrix row engine is invalid.")
    if row.get("status") not in {"answered", "refused", "runtime_failure", "unavailable"}:
        raise ValueError("Matrix row status is invalid.")
    if row.get("consensus") not in CONSENSUS:
        raise ValueError("Matrix row consensus is invalid.")
    correct = row.get("correct")
    if correct is not None and not isinstance(correct, bool):
        raise ValueError("Matrix row correct must be boolean or null.")
    if correct is not None and row.get("status") != "answered":
        raise ValueError("Only answered rows may have binary correctness.")


def _consensus(
    rows: Sequence[Mapping[str, Any]],
    *,
    allowed_judges: Sequence[str] | None = None,
) -> tuple[bool | None, str, list[str], bool | None]:
    allowed = set(allowed_judges) if allowed_judges is not None else None
    latest: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        model = str(row["judge_model"])
        if allowed is None or model in allowed:
            latest[model] = row
    judge_models = sorted(latest)
    if len(judge_models) < 2:
        return None, "insufficient_judges" if judge_models else "not_judged", judge_models, None
    verdicts = [str(latest[model]["verdict"]) for model in judge_models]
    format_valid = all(bool(latest[model].get("format_valid")) for model in judge_models)
    if all(verdict == "correct" for verdict in verdicts):
        return True, "unanimous_correct", judge_models, format_valid
    if all(verdict == "incorrect" for verdict in verdicts):
        return False, "unanimous_incorrect", judge_models, format_valid
    return None, "disagree", judge_models, format_valid


def _load_judge_policy(path: Path) -> dict[str, tuple[str, ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Judge policy must be a JSON object.")
    result: dict[str, tuple[str, ...]] = {}
    for engine, judges in payload.items():
        if not isinstance(engine, str) or not engine or not isinstance(judges, list):
            raise ValueError("Judge policy entries must map engine/model ids to judge arrays.")
        normalized = tuple(str(value) for value in judges if isinstance(value, str) and value)
        if len(normalized) < 2 or len(set(normalized)) != len(normalized):
            raise ValueError("Each judge policy entry requires at least two distinct judges.")
        result[engine] = normalized
    return result


def _assessment_index(path: Path, calibration: Any) -> dict[str, TaskAssessment]:
    result: dict[str, TaskAssessment] = {}
    for row in jsonl_rows(path):
        task_id = str(row.get("id") or "")
        prediction = row.get("prediction")
        if (
            not task_id
            or task_id in result
            or row.get("parse_error") is not None
            or not isinstance(prediction, Mapping)
        ):
            raise ValueError("Assessment rows require unique ids and valid FunctionGemma predictions.")
        result[task_id] = calibration.apply(TaskAssessment.from_mapping(prediction))
    return result


def _judgment_index(paths: Sequence[Path]) -> dict[str, list[Mapping[str, Any]]]:
    result: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for path in paths:
        for row in jsonl_rows(path):
            result[str(row["candidate_id"])].append(row)
    return result


def _task_text(task: Mapping[str, Any]) -> str:
    messages = task.get("messages")
    if not isinstance(messages, list) or len(messages) < 2 or not isinstance(messages[1], Mapping):
        raise ValueError("Task is missing its user text.")
    return str(messages[1]["content"])


def _token(payload: Any, name: str) -> int:
    value = payload.get(name) if isinstance(payload, Mapping) else 0
    return int(value) if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _peak_memory(engine: str) -> float:
    if engine == Engine.GEMMA_E2B.value:
        return 1563.5
    return 0.0


def _optional_string(value: Any) -> str | None:
    return str(value) if isinstance(value, str) and value else None


def _regression_split(value: Any) -> str | None:
    if value is None:
        return None
    if value not in {"train", "validation", "test"}:
        raise ValueError("Task regression_split must be train, validation, test or null.")
    return str(value)


def _report(
    rows: Sequence[Mapping[str, Any]],
    *,
    tasks_path: Path,
    assessments_path: Path,
    calibration_path: Path,
    judge_policy_path: Path,
    competition_snapshot_path: Path,
    candidate_paths: Sequence[Path],
    judgment_paths: Sequence[Path],
    output: Path,
) -> dict[str, Any]:
    by_engine: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        label = str(row.get("model_id") or row["engine"])
        by_engine[label][str(row["consensus"])] += 1
    return {
        "schema_version": "engine-outcome-matrix-report-v1",
        "rows": len(rows),
        "tasks": len({str(row["task_id"]) for row in rows}),
        "binary_outcomes": sum(row.get("correct") is not None for row in rows),
        "missing_outcomes": sum(row.get("correct") is None for row in rows),
        "by_engine": {name: dict(sorted(values.items())) for name, values in sorted(by_engine.items())},
        "tasks_sha256": file_sha256(tasks_path),
        "assessments_sha256": file_sha256(assessments_path),
        "calibration_sha256": file_sha256(calibration_path),
        "judge_policy_sha256": file_sha256(judge_policy_path),
        "competition_snapshot_sha256": file_sha256(competition_snapshot_path),
        "candidate_sha256": {str(path): file_sha256(path) for path in candidate_paths},
        "judgment_sha256": {str(path): file_sha256(path) for path in judgment_paths},
        "matrix_sha256": file_sha256(output),
    }


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
