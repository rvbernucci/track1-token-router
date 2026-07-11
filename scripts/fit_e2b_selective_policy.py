#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import FeatureVector, TaskEnvelope
from router.orchestration.e2b_selective_gate import combine_feature_vectors, extract_e2b_response_signals
from scripts.build_engine_outcome_matrix import _judgment_index, _load_judge_policy
from scripts.championship_ablation import KIMI, _fireworks_candidates, _jsonl, summarize
from scripts.fit_engine_outcome_models import _fit_binary_variant, _predict_binary_variant
from scripts.promote_e2b_policy import _wilson_lower


PRE_THRESHOLDS = (0.20, 0.30, 0.40, 0.50)
POST_THRESHOLDS = (0.75, 0.80, 0.85, 0.90)
L2 = 0.75
MODEL_VARIANT = "logistic_nonlinear"
MINIMUM_VALIDATION_SELECTED = 15
VALIDATION_LOCAL_WILSON_GATE = 0.70
LOCKED_LOCAL_WILSON_GATE = 0.60


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fit a conservative two-stage E2B selective routing policy.")
    parser.add_argument(
        "--matrix",
        type=Path,
        default=Path("reports/generated/amd-pod-e2b-regression-2000/e2b-outcome-matrix.jsonl"),
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("reports/generated/amd-pod-e2b-regression-2000/e2b-candidates-96.jsonl"),
    )
    parser.add_argument("--output", type=Path, default=Path("configs/e2b-selective-policy-v1.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/e2b-selective-policy-report.json"))
    parser.add_argument(
        "--fresh-holdout",
        action="store_true",
        help="Declare that the test split was not previously inspected for this policy family.",
    )
    parser.add_argument(
        "--allow-promotion",
        action="store_true",
        help="Permit default_enabled=true only when every validation/test gate and fresh-holdout gate passes.",
    )
    args = parser.parse_args(argv)
    report, policy = fit_selective_policy(
        root=ROOT,
        matrix_path=_absolute(args.matrix),
        candidates_path=_absolute(args.candidates),
        fresh_holdout=args.fresh_holdout,
        allow_promotion=args.allow_promotion,
    )
    output = _absolute(args.output)
    report_path = _absolute(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(policy, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["decision"], sort_keys=True))
    return 0


def fit_selective_policy(
    *,
    root: Path,
    matrix_path: Path,
    candidates_path: Path,
    fresh_holdout: bool = False,
    allow_promotion: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    matrix = [
        row
        for row in _jsonl(matrix_path)
        if (row.get("model_id") or row.get("engine")) == "gemma4-e2b"
    ]
    if not matrix:
        raise ValueError("E2B outcome matrix is empty.")
    candidates = {str(row["id"]): row for row in _jsonl(candidates_path)}
    rows = [_augment_row(row, candidates) for row in matrix]
    train = [row for row in rows if row["regression_split"] == "train"]
    validation = [row for row in rows if row["regression_split"] == "validation"]
    locked = [row for row in rows if row["regression_split"] == "test"]
    if not train or not validation or not locked:
        raise ValueError("Selective E2B fitting requires train, validation and test rows.")

    pre_names = list(train[0]["task_features"]["names"])
    post_names = list(train[0]["combined_features"]["names"])
    pre_coefficients, pre_model_names = _fit_binary_variant(
        [_fit_row(row, "task_features") for row in train],
        pre_names,
        variant=MODEL_VARIANT,
        l2=L2,
    )
    post_coefficients, post_model_names = _fit_binary_variant(
        [_fit_row(row, "combined_features") for row in train],
        post_names,
        variant=MODEL_VARIANT,
        l2=L2,
    )
    scored = {
        split: _score_rows(
            split_rows,
            pre_names=pre_names,
            pre_coefficients=pre_coefficients,
            post_names=post_names,
            post_coefficients=post_coefficients,
        )
        for split, split_rows in (("validation", validation), ("test", locked))
    }
    remote, tasks = _load_kimi_evidence(root)
    validation_candidates = [
        _threshold_metrics(
            scored["validation"],
            pre_threshold=pre,
            post_threshold=post,
            split="validation",
            remote=remote,
            tasks=tasks,
        )
        for pre in PRE_THRESHOLDS
        for post in POST_THRESHOLDS
    ]
    locked_grid_diagnostic = [
        _threshold_metrics(
            scored["test"],
            pre_threshold=float(candidate["pre_threshold"]),
            post_threshold=float(candidate["post_threshold"]),
            split="test",
            remote=remote,
            tasks=tasks,
        )
        for candidate in validation_candidates
    ]
    selected = select_validation_candidate(validation_candidates)
    locked_metrics = _threshold_metrics(
        scored["test"],
        pre_threshold=float(selected["pre_threshold"]),
        post_threshold=float(selected["post_threshold"]),
        split="test",
        remote=remote,
        tasks=tasks,
    )
    locked_pass = (
        int(locked_metrics["selected_rows"]) >= MINIMUM_VALIDATION_SELECTED
        and float(locked_metrics["local_wilson_lower_95"]) >= LOCKED_LOCAL_WILSON_GATE
    )
    promoted = bool(allow_promotion and fresh_holdout and selected["validation_feasible"] and locked_pass)
    reason = (
        "Selective E2B passed fresh validation and locked promotion gates."
        if promoted
        else "Selective E2B remains disabled until a genuinely fresh holdout passes the binary local-accuracy gate."
    )
    policy = {
        "schema_version": "e2b-selective-policy-v1",
        "default_enabled": promoted,
        "thresholds": {
            "pre_probe": selected["pre_threshold"],
            "post_accept": selected["post_threshold"],
        },
        "models": {
            "pre_response": {
                "variant": MODEL_VARIANT,
                "feature_names": pre_model_names,
                "coefficients": pre_coefficients,
            },
            "post_response": {
                "variant": MODEL_VARIANT,
                "feature_names": post_model_names,
                "coefficients": post_coefficients,
            },
        },
        "fit": {
            "label_policy": "e2b_correct_true_else_escalate",
            "l2": L2,
            "matrix_sha256": _sha256(matrix_path),
            "candidates_sha256": _sha256(candidates_path),
            "train_rows": len(train),
            "validation_rows": len(validation),
            "locked_rows": len(locked),
        },
        "evidence": {
            "validation": selected,
            "locked_diagnostic": locked_metrics,
            "fresh_holdout": fresh_holdout,
            "promotion_explicitly_allowed": allow_promotion,
            "locked_test_reused_by_prior_policy_family": not fresh_holdout,
        },
        "reason": reason,
    }
    report = {
        "schema_version": "e2b-selective-policy-report-v1",
        "candidate_grid": validation_candidates,
        "locked_grid_diagnostic": locked_grid_diagnostic,
        "selected_validation_candidate": selected,
        "locked_diagnostic": locked_metrics,
        "decision": {
            "promoted": promoted,
            "validation_pass": bool(selected["validation_feasible"]),
            "locked_pass": locked_pass,
            "fresh_holdout": fresh_holdout,
            "reason": reason,
        },
    }
    return report, policy


def select_validation_candidate(candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    feasible = [candidate for candidate in candidates if candidate.get("validation_feasible")]
    pool = feasible or list(candidates)
    if not pool:
        raise ValueError("Threshold candidate grid is empty.")
    return dict(
        max(
            pool,
            key=lambda row: (
                bool(row.get("validation_feasible")),
                float(row["local_wilson_lower_95"]),
                float(row["local_accuracy"]),
                int(row["selected_rows"]),
                int(row["saved_fireworks_tokens"]),
                float(row["post_threshold"]),
                float(row["pre_threshold"]),
            ),
        )
    )


def _augment_row(row: Mapping[str, Any], candidates: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    candidate_id = str(row.get("candidate_id") or "")
    if candidate_id not in candidates:
        raise ValueError(f"Missing E2B candidate {candidate_id!r}.")
    candidate = candidates[candidate_id]
    task = TaskEnvelope(id=str(row["task_id"]), input_text=str(candidate["task_text"]))
    signals = extract_e2b_response_signals(task, str(candidate.get("answer") or ""))
    task_features = FeatureVector.from_mapping(row["features"])
    combined = combine_feature_vectors(task_features, signals.features)
    return {
        **dict(row),
        "correct": row.get("correct") is True,
        "task_features": task_features.to_dict(),
        "combined_features": combined.to_dict(),
        "mechanically_valid": signals.mechanically_valid,
        "response_signals": signals.to_dict(),
    }


def _fit_row(row: Mapping[str, Any], key: str) -> dict[str, Any]:
    return {"correct": bool(row["correct"]), "features": row[key]}


def _score_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    pre_names: Sequence[str],
    pre_coefficients: Sequence[float],
    post_names: Sequence[str],
    post_coefficients: Sequence[float],
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for row in rows:
        pre_row = _fit_row(row, "task_features")
        post_row = _fit_row(row, "combined_features")
        scored.append(
            {
                **dict(row),
                "pre_probability": _predict_binary_variant(pre_row, pre_names, MODEL_VARIANT, pre_coefficients),
                "post_probability": _predict_binary_variant(post_row, post_names, MODEL_VARIANT, post_coefficients),
            }
        )
    return scored


def _threshold_metrics(
    rows: Sequence[Mapping[str, Any]],
    *,
    pre_threshold: float,
    post_threshold: float,
    split: str,
    remote: Mapping[tuple[str, str], Mapping[str, Any]],
    tasks: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    selected = [
        row
        for row in rows
        if row["mechanically_valid"]
        and float(row["pre_probability"]) >= pre_threshold
        and float(row["post_probability"]) >= post_threshold
    ]
    selected_by_id = {str(row["task_id"]): row for row in selected}
    local_correct = sum(row["correct"] is True for row in selected)
    kimi_rows: list[dict[str, Any]] = []
    hybrid_rows: list[dict[str, Any]] = []
    for task_id, task in tasks.items():
        if task.get("regression_split") != split:
            continue
        remote_row = dict(remote[(task_id, KIMI)])
        kimi_rows.append(remote_row)
        local = selected_by_id.get(task_id)
        if local is None:
            hybrid_rows.append(remote_row)
        else:
            hybrid_rows.append(
                {
                    "correct": local["correct"],
                    "tokens": 0,
                    "latency_ms": float(local.get("latency_ms") or 0.0),
                    "local": True,
                    "model": "gemma4-e2b",
                }
            )
    kimi = summarize(kimi_rows)
    hybrid = summarize(hybrid_rows)
    local_wilson = _wilson_lower(local_correct, len(selected))
    by_intent: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "selected": 0,
            "e2b_correct": 0,
            "kimi_correct": 0,
            "both_correct": 0,
            "e2b_only_correct": 0,
            "kimi_only_correct": 0,
            "both_not_correct": 0,
        }
    )
    for task_id, local in selected_by_id.items():
        intent = str(local["assessment"]["intent"])
        e2b_correct = local["correct"] is True
        kimi_correct = remote[(task_id, KIMI)].get("correct") is True
        bucket = by_intent[intent]
        bucket["selected"] += 1
        bucket["e2b_correct"] += int(e2b_correct)
        bucket["kimi_correct"] += int(kimi_correct)
        if e2b_correct and kimi_correct:
            bucket["both_correct"] += 1
        elif e2b_correct:
            bucket["e2b_only_correct"] += 1
        elif kimi_correct:
            bucket["kimi_only_correct"] += 1
        else:
            bucket["both_not_correct"] += 1
    validation_feasible = (
        len(selected) >= MINIMUM_VALIDATION_SELECTED
        and local_wilson >= VALIDATION_LOCAL_WILSON_GATE
    )
    return {
        "pre_threshold": pre_threshold,
        "post_threshold": post_threshold,
        "probed_rows": sum(float(row["pre_probability"]) >= pre_threshold for row in rows),
        "selected_rows": len(selected),
        "selected_coverage": len(selected) / len(rows),
        "local_correct": local_correct,
        "local_accuracy": local_correct / len(selected) if selected else 0.0,
        "local_wilson_lower_95": local_wilson,
        "kimi": kimi,
        "hybrid": hybrid,
        "saved_fireworks_tokens": int(kimi["fireworks_tokens"]) - int(hybrid["fireworks_tokens"]),
        "selected_by_intent": dict(sorted(by_intent.items())),
        "validation_feasible": validation_feasible,
    }


def _load_kimi_evidence(root: Path) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, dict[str, Any]]]:
    run = root / "data/championship-ablation"
    judgments = _judgment_index([run / "fireworks-judgments.jsonl"])
    policy = _load_judge_policy(root / "configs/fireworks-baseline-judge-policy.json")
    remote = _fireworks_candidates([run / "kimi-candidates.jsonl"], judgments=judgments, judge_policy=policy)
    tasks = {str(row["id"]): row for row in _jsonl(run / "tasks.jsonl")}
    return remote, tasks


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
