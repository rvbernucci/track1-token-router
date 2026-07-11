#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import Intent, RequestedOutputShape, TaskEnvelope
from router.orchestration.assessment import approximate_token_count, detect_requested_output_shape
from router.orchestration.code_verifier import infer_code_task_contract
from router.orchestration.proof_engine import solve_with_proof
from router.orchestration.solvers import solve_deterministic
from scripts.adjudicate_e2b_regression_v2 import _mechanical
from scripts.promote_e2b_policy import _wilson_lower


SCHEMA = "e2b-local-adjudication-v2-candidate"
SCORE_NAMES = (
    "deterministic_fit",
    "reasoning_demand",
    "knowledge_uncertainty",
    "generation_demand",
    "format_complexity",
)
PERTURBATION_RADIUS = 0.02
ABSTENTION_BAND = 0.02
BOOTSTRAPS = 24
TOKEN_OUTPUT_ESTIMATE = 96


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fit the sealed-firewall two-stage local routing policy V2.")
    parser.add_argument("--root", type=Path, default=Path("evals/e2b-regression-v2-adjudication"))
    parser.add_argument("--output", type=Path, default=Path("configs/e2b-local-adjudication-v2-candidate.json"))
    parser.add_argument("--json-report", type=Path, default=Path("reports/generated/e2b-regression-v2-calibration.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/e2b-regression-v2-calibration.md"))
    parser.add_argument("--fresh-holdout", choices=("true", "false"), default="false")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.fresh_holdout != "false":
        raise SystemExit("Sprint 58 may not open or declare the final holdout fresh.")
    report, policy = fit(_absolute(args.root))
    _write_json(_absolute(args.output), policy)
    _write_json(_absolute(args.json_report), report)
    report_path = _absolute(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_markdown(report), encoding="utf-8")
    result = check(_absolute(args.root), _absolute(args.output), _absolute(args.json_report)) if args.check else report["decision"]
    print(json.dumps(result, sort_keys=True))
    return 0


def fit(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate_path = root / "development" / "candidates.jsonl"
    label_path = root / "development" / "labels.jsonl"
    metadata_path = ROOT / "evals/e2b-regression-v2/metadata.jsonl"
    candidates = {str(row["task_id"]): row for row in _jsonl(candidate_path)}
    labels = {str(row["task_id"]): row for row in _jsonl(label_path)}
    metadata = {str(row["task_id"]): row for row in _jsonl(metadata_path)}
    if set(candidates) != set(labels) or not set(labels) <= set(metadata):
        raise ValueError("Development candidates, labels and metadata are not aligned.")
    rows = [_row(labels[task_id], candidates[task_id], metadata[task_id]) for task_id in sorted(labels)]
    train = [row for row in rows if row["split"] == "train" and row["assessment_valid"]]
    validation = [row for row in rows if row["split"] == "validation" and row["assessment_valid"]]
    invalid = [row for row in rows if not row["assessment_valid"]]
    if len(train) != 1192 or len(validation) != 400 or len(invalid) != 8:
        raise ValueError("Unexpected valid/invalid development partition.")
    split_audit = _split_audit(train, validation)
    if not split_audit["passed"]:
        raise ValueError("Template or mutation lineage leakage between train and validation.")
    names = list(train[0]["features"]["names"])
    if len(names) > 24:
        raise ValueError("Stage A feature contract exceeds 24 dimensions.")

    deterministic = _fit_target(train, validation, names, "deterministic_target", monotonic="deterministic")
    e2b = _fit_target(train, validation, names, "e2b_target", monotonic="e2b")
    scored = _score(validation, deterministic, e2b)
    thresholds = _select_thresholds(scored)
    stress = _stress(train, validation, deterministic, e2b, thresholds)
    calibration = {
        "deterministic": _calibration([(float(row["deterministic_target"]), row["p_deterministic"]) for row in scored]),
        "e2b": _calibration([(float(row["e2b_target"]), row["p_e2b"]) for row in scored]),
    }
    metrics = _route_metrics(scored, thresholds)
    mixes = _mixes(scored, thresholds)
    utility = _expected_utility(scored, thresholds)
    token_bootstrap = _token_bootstrap(scored, thresholds)
    enabled_families = sorted(
        family
        for family, lineages in _family_lineages(train + validation).items()
        if len(lineages) >= 100 and family != "none"
    )
    gates = {
        "development_only_fit": True,
        "split_groups_disjoint": split_audit["passed"],
        "feature_dimensions_at_most_24": len(names) <= 24,
        "invalid_assessment_routes_remote": len(invalid) == 8,
        "local_release_precision_at_least_95pct": metrics["e2b_release_precision"] >= 0.95,
        "wilson_lower_at_least_90pct": metrics["e2b_release_wilson_lower_95"] >= 0.90,
        "zero_verifier_invalid_releases": metrics["verifier_invalid_releases"] == 0,
        "zero_unsupported_factual_releases": metrics["unsupported_factual_releases"] == 0,
        "probability_flip_rate_below_5pct": stress["probability_perturbation"]["flip_rate"] < 0.05,
        "score_shift_flip_rate_below_5pct": stress["score_shift"]["flip_rate"] < 0.05,
        "bootstrap_route_agreement_at_least_95pct": stress["bootstrap"]["route_agreement"] >= 0.95,
        "enabled_families_have_100_lineages": all(
            len(_family_lineages(train + validation)[family]) >= 100 for family in enabled_families
        ),
        "token_savings_lower_bound_positive": token_bootstrap["tokens_saved_ci95"][0] > 0,
    }
    nomination_passed = all(gates.values())
    reason = (
        "Candidate meets development nomination gates but remains disabled until Sprint 59 opens the sealed holdout."
        if nomination_passed
        else "Candidate remains disabled; development evidence does not satisfy every championship safety gate."
    )
    policy = {
        "schema_version": SCHEMA,
        "default_enabled": False,
        "invalid_assessment_route": "fireworks",
        "architecture": ["deterministic_regression", "deterministic_proof", "e2b_regression", "answer_contract_and_hard_verifier", "fireworks"],
        "feature_contract": {"stage_a": names, "dimensions": len(names), "input_only": True},
        "models": {"deterministic": deterministic["artifact"], "e2b": e2b["artifact"]},
        "thresholds": {
            **thresholds,
            "probability_perturbation_radius": PERTURBATION_RADIUS,
            "abstention_band": ABSTENTION_BAND,
        },
        "enabled_verifier_families": enabled_families,
        "hard_release_contract": {
            "answer_contract_valid": True,
            "registered_verifier_required": True,
            "verifier_acceptance_required": True,
            "open_world_factual_remote": True,
            "probability_cannot_override_failed_evidence": True,
        },
        "fit": {
            "train_rows": len(train),
            "validation_rows": len(validation),
            "invalid_assessment_rows": len(invalid),
            "threshold_selection_split": "validation",
            "final_holdout_accessed": False,
            "candidate_sha256": _sha256(candidate_path),
            "labels_sha256": _sha256(label_path),
            "metadata_sha256": _sha256(metadata_path),
        },
        "expected_utility": utility,
        "evidence": {"nomination_gates": gates, "nomination_passed": nomination_passed},
        "reason": reason,
    }
    report = {
        "schema_version": "e2b-regression-v2-calibration-v1",
        "split_audit": split_audit,
        "grouped_folds": _grouped_fold_audit(train),
        "rows": {"train": len(train), "validation": len(validation), "invalid_remote_fallback": len(invalid)},
        "targets": {
            "train_e2b_positive": sum(row["e2b_target"] for row in train),
            "validation_e2b_positive": sum(row["e2b_target"] for row in validation),
            "train_deterministic_positive": sum(row["deterministic_target"] for row in train),
            "validation_deterministic_positive": sum(row["deterministic_target"] for row in validation),
        },
        "model_comparison": {"deterministic": deterministic["diagnostics"], "e2b": e2b["diagnostics"]},
        "calibration": calibration,
        "thresholds": thresholds,
        "validation": metrics,
        "stress": stress,
        "input_mixes": mixes,
        "expected_utility": utility,
        "token_bootstrap": token_bootstrap,
        "enabled_verifier_families": enabled_families,
        "decision": {"nominated": nomination_passed, "default_enabled": False, "gates": gates, "reason": reason},
    }
    return report, policy


def check(root: Path, policy_path: Path, report_path: Path) -> dict[str, Any]:
    policy = json.loads(policy_path.read_text())
    report = json.loads(report_path.read_text())
    source = Path(__file__).read_text(encoding="utf-8")
    gates = {
        "schema": policy.get("schema_version") == SCHEMA,
        "disabled_until_sprint59": policy.get("default_enabled") is False,
        "invalid_assessment_remote": policy.get("invalid_assessment_route") == "fireworks",
        "no_sealed_path_in_fit_source": re.search(r"root\s*/\s*['\"]sealed", source, re.IGNORECASE) is None,
        "report_development_only": report.get("rows") == {"invalid_remote_fallback": 8, "train": 1192, "validation": 400},
        "candidate_hash": policy["fit"]["candidate_sha256"] == _sha256(root / "development/candidates.jsonl"),
        "label_hash": policy["fit"]["labels_sha256"] == _sha256(root / "development/labels.jsonl"),
        "feature_bound": int(policy["feature_contract"]["dimensions"]) <= 24,
        "perturbation_radius": float(policy["thresholds"]["probability_perturbation_radius"]) >= 0.02,
        "abstention_band": float(policy["thresholds"]["abstention_band"]) >= 0.02,
        "hard_gate_cannot_be_bypassed": policy["hard_release_contract"]["probability_cannot_override_failed_evidence"] is True,
    }
    if not all(gates.values()):
        raise ValueError(f"Sprint 58 checks failed: {[name for name, passed in gates.items() if not passed]}")
    return {"passed": True, "gates": gates, "nomination_passed": report["decision"]["nominated"]}


def _row(label: Mapping[str, Any], candidate: Mapping[str, Any], metadata: Mapping[str, Any]) -> dict[str, Any]:
    assessment = label.get("functiongemma_assessment")
    valid = bool(label.get("assessment_valid")) and isinstance(assessment, Mapping)
    features = _features(candidate["task_text"], assessment) if valid else None
    task = TaskEnvelope(id=str(label["task_id"]), input_text=str(candidate["task_text"]))
    solver = solve_deterministic(task) if valid else None
    deterministic_target = False
    if solver is not None:
        proof = _mechanical(
            {"reference_answer": candidate["reference_answer"], "output_shape": candidate["output_shape"]},
            solver.answer,
            True,
            str(candidate["category"]),
        )
        deterministic_target = proof["verdict"] == "correct"
    return {
        "task_id": label["task_id"],
        "split": label["split"],
        "category": label["category"],
        "assessment_valid": valid,
        "assessment": assessment,
        "features": features,
        "e2b_target": bool(label["binary_label"]),
        "deterministic_target": deterministic_target,
        "contract_valid": bool(label["contract_valid"]),
        "evidence": candidate["local_verifier_evidence"],
        "mutation_lineage": metadata["mutation_lineage"],
        "template_family": metadata["template_family"],
        "prompt": candidate["task_text"],
        "input_tokens": approximate_token_count(str(candidate["task_text"])),
    }


def _features(prompt: str, assessment: Mapping[str, Any]) -> dict[str, Any]:
    intent = str(assessment["intent"])
    scores = assessment["scores"]
    names: list[str] = []
    values: list[float] = []
    for item in Intent:
        names.append(f"intent.{item.value}")
        values.append(float(intent == item.value))
    for name in SCORE_NAMES:
        names.append(f"score.{name}")
        values.append(float(scores[name]) / 10.0)
    shape = detect_requested_output_shape(prompt)
    for item in RequestedOutputShape:
        names.append(f"shape.{item.value}")
        values.append(float(shape is item))
    names.extend(("struct.input_tokens_log", "struct.deadline_ratio", "struct.registered_verifier_available"))
    values.extend((min(1.0, math.log1p(approximate_token_count(prompt)) / math.log1p(8192)), 1.0, float(_pre_verifier_available(prompt))))
    return {"names": names, "values": values}


def _pre_verifier_available(prompt: str) -> bool:
    task = TaskEnvelope(input_text=prompt)
    if infer_code_task_contract(task) is not None or solve_with_proof(task) is not None:
        return True
    lowered = prompt.casefold()
    return bool(re.search(r"\b(?:sentiment|summari[sz]|extract|entities|use only the context|according to the passage)\b", lowered))


def _fit_target(train: Sequence[Mapping[str, Any]], validation: Sequence[Mapping[str, Any]], names: Sequence[str], target: str, *, monotonic: str) -> dict[str, Any]:
    variants: dict[str, dict[str, Any]] = {}
    artifacts: dict[str, dict[str, Any]] = {}
    for name, l1, l2, constrained in (
        ("l1_logistic", 0.02, 0.0, False),
        ("l2_logistic", 0.0, 0.75, False),
        ("monotonic_logistic", 0.0, 0.75, True),
    ):
        weights = _logistic_fit(train, target, l1=l1, l2=l2)
        if constrained:
            weights = _constrain(weights, names, monotonic)
        pairs = [(float(row[target]), _predict(weights, row["features"]["values"])) for row in validation]
        variants[name] = _calibration(pairs)
        variants[name]["nonzero_coefficients"] = sum(abs(value) > 1e-8 for value in weights[1:])
        variants[name]["maximum_abs_coefficient"] = max(abs(value) for value in weights)
        variants[name]["perfect_separation_artifact"] = bool(
            variants[name]["brier"] < 1e-8 and variants[name]["maximum_abs_coefficient"] > 20.0
        )
        artifacts[name] = {"variant": name, "feature_names": ["bias", *names], "coefficients": weights}
    eligible = [name for name in variants if not variants[name]["perfect_separation_artifact"]]
    if not eligible:
        raise ValueError("All regression candidates exhibit perfect-separation artifacts.")
    selected = min(eligible, key=lambda name: (variants[name]["brier"], variants[name]["ece"], variants[name]["nonzero_coefficients"]))
    bootstrap = _coefficient_bootstrap(train, target, names, selected, monotonic)
    artifact = artifacts[selected]
    artifact["validation_calibration"] = _platt(validation, target, artifact["coefficients"])
    return {"artifact": artifact, "diagnostics": {"variants": variants, "selected": selected, "coefficient_bootstrap": bootstrap}}


def _logistic_fit(rows: Sequence[Mapping[str, Any]], target: str, *, l1: float, l2: float, iterations: int = 420) -> list[float]:
    dimensions = len(rows[0]["features"]["values"]) + 1
    weights = [0.0] * dimensions
    rate = 0.18
    for iteration in range(iterations):
        gradients = [0.0] * dimensions
        for row in rows:
            x = [1.0, *row["features"]["values"]]
            error = _sigmoid(sum(a * b for a, b in zip(weights, x, strict=True))) - float(row[target])
            for index, value in enumerate(x):
                gradients[index] += error * value
        step = rate / math.sqrt(1.0 + iteration / 80.0)
        for index in range(dimensions):
            gradient = gradients[index] / len(rows) + (l2 * weights[index] / len(rows) if index else 0.0)
            value = weights[index] - step * gradient
            if index and l1:
                value = math.copysign(max(0.0, abs(value) - step * l1 / len(rows)), value)
            weights[index] = value
    return weights


def _constrain(weights: Sequence[float], names: Sequence[str], target: str) -> list[float]:
    result = list(weights)
    expected = {
        "deterministic": {"score.deterministic_fit": 1, "score.reasoning_demand": -1, "score.knowledge_uncertainty": -1, "score.generation_demand": -1, "score.format_complexity": -1},
        "e2b": {"score.deterministic_fit": 1, "score.reasoning_demand": -1, "score.knowledge_uncertainty": -1, "score.generation_demand": -1, "score.format_complexity": -1},
    }[target]
    for index, name in enumerate(names, start=1):
        sign = expected.get(name)
        if sign == 1:
            result[index] = max(0.0, result[index])
        elif sign == -1:
            result[index] = min(0.0, result[index])
    return result


def _platt(rows: Sequence[Mapping[str, Any]], target: str, coefficients: Sequence[float]) -> dict[str, float]:
    proxy = [{"features": {"values": [_logit(_predict(coefficients, row["features"]["values"]))]}, target: row[target]} for row in rows]
    fitted = _logistic_fit(proxy, target, l1=0.0, l2=0.25, iterations=500)
    return {"intercept": fitted[0], "slope": fitted[1], "fit_split": "validation"}


def _score(rows: Sequence[Mapping[str, Any]], deterministic: Mapping[str, Any], e2b: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        item = dict(row)
        item["p_deterministic"] = _calibrated_predict(deterministic["artifact"], row["features"]["values"])
        item["p_e2b"] = _calibrated_predict(e2b["artifact"], row["features"]["values"])
        result.append(item)
    return result


def _calibrated_predict(artifact: Mapping[str, Any], values: Sequence[float]) -> float:
    raw = _predict(artifact["coefficients"], values)
    calibration = artifact["validation_calibration"]
    return _sigmoid(float(calibration["intercept"]) + float(calibration["slope"]) * _logit(raw))


def _select_thresholds(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    options = [round(0.50 + index * 0.01, 2) for index in range(46)]
    deterministic = max(options, key=lambda threshold: _det_threshold_key(rows, threshold))
    e2b = max(options, key=lambda threshold: _e2b_threshold_key(rows, threshold))
    return {"deterministic_probe": deterministic, "e2b_probe": e2b, "e2b_release": e2b + ABSTENTION_BAND}


def _det_threshold_key(rows: Sequence[Mapping[str, Any]], threshold: float) -> tuple[float, ...]:
    selected = [row for row in rows if row["p_deterministic"] >= threshold]
    positives = sum(row["deterministic_target"] for row in selected)
    return (_wilson_lower(positives, len(selected)), positives, -len(selected), threshold)


def _e2b_threshold_key(rows: Sequence[Mapping[str, Any]], threshold: float) -> tuple[float, ...]:
    selected = [row for row in rows if _e2b_released(row, threshold + ABSTENTION_BAND)]
    correct = sum(row["e2b_target"] for row in selected)
    return (_wilson_lower(correct, len(selected)), correct / len(selected) if selected else 0.0, len(selected), threshold)


def _e2b_released(row: Mapping[str, Any], threshold: float) -> bool:
    evidence = row["evidence"]
    return bool(
        row["p_e2b"] >= threshold
        and row["contract_valid"]
        and evidence["hard_gate_passed"] is True
        and row["category"] != "factual_qa"
    )


def _route_metrics(rows: Sequence[Mapping[str, Any]], thresholds: Mapping[str, float]) -> dict[str, Any]:
    deterministic = [row for row in rows if row["p_deterministic"] >= thresholds["deterministic_probe"] and row["deterministic_target"]]
    e2b = [row for row in rows if row not in deterministic and _e2b_released(row, thresholds["e2b_release"])]
    correct = sum(row["e2b_target"] for row in e2b)
    return {
        "rows": len(rows),
        "deterministic_releases": len(deterministic),
        "e2b_releases": len(e2b),
        "e2b_release_precision": correct / len(e2b) if e2b else 0.0,
        "e2b_release_wilson_lower_95": _wilson_lower(correct, len(e2b)),
        "local_coverage": (len(deterministic) + len(e2b)) / len(rows),
        "verifier_invalid_releases": sum(not row["evidence"]["hard_gate_passed"] for row in e2b),
        "unsupported_factual_releases": sum(row["category"] == "factual_qa" for row in e2b),
    }


def _stress(train: Sequence[Mapping[str, Any]], validation: Sequence[Mapping[str, Any]], deterministic: Mapping[str, Any], e2b: Mapping[str, Any], thresholds: Mapping[str, float]) -> dict[str, Any]:
    scored = _score(validation, deterministic, e2b)
    perturbations: dict[str, Any] = {}
    for mode in ("deterministic_only", "e2b_only", "joint"):
        comparisons = flips = 0
        for row in scored:
            base = _route(row, thresholds)
            for delta in (-PERTURBATION_RADIUS, PERTURBATION_RADIUS):
                changed = dict(row)
                if mode in {"deterministic_only", "joint"}:
                    changed["p_deterministic"] = max(0.0, min(1.0, row["p_deterministic"] + delta))
                if mode in {"e2b_only", "joint"}:
                    changed["p_e2b"] = max(0.0, min(1.0, row["p_e2b"] + delta))
                flips += int(base != _route(changed, thresholds))
                comparisons += 1
        perturbations[mode] = {"comparisons": comparisons, "flips": flips, "flip_rate": flips / comparisons}
    score_flips = score_comparisons = 0
    for row in validation:
        base = _route(next(item for item in scored if item["task_id"] == row["task_id"]), thresholds)
        for score_name in SCORE_NAMES:
            for delta in (-1, 1):
                altered = dict(row)
                assessment = json.loads(json.dumps(row["assessment"]))
                assessment["scores"][score_name] = max(0, min(10, assessment["scores"][score_name] + delta))
                altered["features"] = _features(row["prompt"], assessment)
                shifted = _score([altered], deterministic, e2b)[0]
                score_flips += int(base != _route(shifted, thresholds))
                score_comparisons += 1
    bootstrap = _bootstrap_route_agreement(train, validation, e2b, thresholds)
    return {
        "probability_perturbation": {"radius": PERTURBATION_RADIUS, "modes": perturbations, **perturbations["joint"]},
        "score_shift": {"delta": 1, "comparisons": score_comparisons, "flips": score_flips, "flip_rate": score_flips / score_comparisons},
        "bootstrap": bootstrap,
    }


def _bootstrap_route_agreement(train: Sequence[Mapping[str, Any]], validation: Sequence[Mapping[str, Any]], baseline: Mapping[str, Any], thresholds: Mapping[str, float]) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in train:
        grouped[row["mutation_lineage"]].append(row)
    lineages = sorted(grouped)
    baseline_routes = [_calibrated_predict(baseline["artifact"], row["features"]["values"]) >= thresholds["e2b_probe"] for row in validation]
    rng = random.Random(58059)
    agreements: list[float] = []
    for _ in range(BOOTSTRAPS):
        sample = [row for _ in lineages for row in grouped[rng.choice(lineages)]]
        weights = _logistic_fit(sample, "e2b_target", l1=0.0, l2=0.75, iterations=120)
        routes = [_predict(weights, row["features"]["values"]) >= thresholds["e2b_probe"] for row in validation]
        agreements.append(sum(left == right for left, right in zip(baseline_routes, routes, strict=True)) / len(routes))
    return {"resamples": BOOTSTRAPS, "route_agreement": statistics.fmean(agreements), "minimum_route_agreement": min(agreements)}


def _coefficient_bootstrap(rows: Sequence[Mapping[str, Any]], target: str, names: Sequence[str], selected: str, monotonic: str) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["mutation_lineage"]].append(row)
    lineages = sorted(grouped)
    rng = random.Random(58058)
    samples: list[list[float]] = []
    for _ in range(20):
        sample = [row for _ in lineages for row in grouped[rng.choice(lineages)]]
        weights = _logistic_fit(sample, target, l1=0.02 if selected == "l1_logistic" else 0.0, l2=0.75 if selected != "l1_logistic" else 0.0, iterations=120)
        if selected == "monotonic_logistic":
            weights = _constrain(weights, names, monotonic)
        samples.append(weights)
    return {
        "resamples": len(samples),
        "sign_stability": {
            name: max(sum(sample[index] >= 0 for sample in samples), sum(sample[index] <= 0 for sample in samples)) / len(samples)
            for index, name in enumerate(["bias", *names])
        },
    }


def _route(row: Mapping[str, Any], thresholds: Mapping[str, float]) -> str:
    if row["p_deterministic"] >= thresholds["deterministic_probe"] and row["deterministic_target"]:
        return "deterministic"
    if _e2b_released(row, thresholds["e2b_release"]):
        return "e2b"
    return "fireworks"


def _expected_utility(rows: Sequence[Mapping[str, Any]], thresholds: Mapping[str, float]) -> dict[str, Any]:
    local = [row for row in rows if _route(row, thresholds) != "fireworks"]
    selected = [row for row in local if _route(row, thresholds) == "e2b"]
    tokens = sum(row["input_tokens"] + TOKEN_OUTPUT_ESTIMATE for row in local)
    latency_penalty = len(selected) * 10.445
    risk_penalty = sum((1.0 - row["p_e2b"]) * 100 for row in selected)
    return {
        "fireworks_tokens_avoided": tokens,
        "e2b_p50_latency_seconds": 5.568,
        "e2b_p95_latency_seconds": 10.445,
        "deadline_exhaustion_risk": len(selected) * 10.445 / 600.0,
        "latency_penalty": latency_penalty,
        "risk_penalty": risk_penalty,
        "utility": tokens - latency_penalty - risk_penalty,
        "immediate_fireworks_utility": 0.0,
        "accuracy_gate_precedes_utility": True,
    }


def _token_bootstrap(rows: Sequence[Mapping[str, Any]], thresholds: Mapping[str, float]) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["mutation_lineage"]].append(row)
    lineages = sorted(grouped)
    rng = random.Random(58159)
    values = []
    for _ in range(400):
        sample = [row for _ in lineages for row in grouped[rng.choice(lineages)]]
        values.append(sum(row["input_tokens"] + TOKEN_OUTPUT_ESTIMATE for row in sample if _route(row, thresholds) != "fireworks"))
    return {"resamples": len(values), "tokens_saved_ci95": [_percentile(values, 2.5), _percentile(values, 97.5)]}


def _mixes(rows: Sequence[Mapping[str, Any]], thresholds: Mapping[str, float]) -> dict[str, Any]:
    weights = {
        "balanced": {},
        "sentiment_ner_heavy": {"sentiment": 4, "ner": 4},
        "code_math_heavy": {"code_generation": 4, "code_debugging": 4, "math_reasoning": 4},
    }
    result = {}
    for name, mapping in weights.items():
        sample = [row for row in rows for _ in range(mapping.get(row["category"], 1))]
        result[name] = _route_metrics(sample, thresholds)
    return result


def _split_audit(train: Sequence[Mapping[str, Any]], validation: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    train_lineages = {row["mutation_lineage"] for row in train}
    validation_lineages = {row["mutation_lineage"] for row in validation}
    train_templates = {row["template_family"] for row in train}
    validation_templates = {row["template_family"] for row in validation}
    return {
        "passed": not (train_lineages & validation_lineages) and not (train_templates & validation_templates),
        "train_lineages": len(train_lineages),
        "validation_lineages": len(validation_lineages),
        "lineage_overlap": len(train_lineages & validation_lineages),
        "template_overlap": len(train_templates & validation_templates),
    }


def _grouped_fold_audit(rows: Sequence[Mapping[str, Any]], folds: int = 5) -> dict[str, Any]:
    assignments: dict[str, int] = {}
    for lineage in sorted({str(row["mutation_lineage"]) for row in rows}):
        digest = hashlib.sha256(lineage.encode()).digest()
        assignments[lineage] = int.from_bytes(digest[:4], "big") % folds
    details = []
    for fold in range(folds):
        held = [row for row in rows if assignments[str(row["mutation_lineage"])] == fold]
        fitted = [row for row in rows if assignments[str(row["mutation_lineage"])] != fold]
        details.append({
            "fold": fold,
            "fit_rows": len(fitted),
            "held_out_rows": len(held),
            "held_out_lineages": len({row["mutation_lineage"] for row in held}),
            "held_out_e2b_positive": sum(row["e2b_target"] for row in held),
            "lineage_overlap": len({row["mutation_lineage"] for row in held} & {row["mutation_lineage"] for row in fitted}),
        })
    return {"folds": folds, "group_key": "mutation_lineage", "all_disjoint": all(not row["lineage_overlap"] for row in details), "details": details}


def _family_lineages(rows: Sequence[Mapping[str, Any]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        result[str(row["evidence"]["verifier_family"])].add(str(row["mutation_lineage"]))
    return result


def _calibration(pairs: Sequence[tuple[float, float]]) -> dict[str, Any]:
    brier = sum((prediction - actual) ** 2 for actual, prediction in pairs) / len(pairs)
    bins = []
    ece = 0.0
    for lower in (0.0, 0.2, 0.4, 0.6, 0.8):
        bucket = [(actual, prediction) for actual, prediction in pairs if lower <= prediction < lower + 0.2 or (lower == 0.8 and prediction == 1.0)]
        if bucket:
            confidence = statistics.fmean(prediction for _, prediction in bucket)
            empirical = statistics.fmean(actual for actual, _ in bucket)
            ece += len(bucket) / len(pairs) * abs(confidence - empirical)
            bins.append({"lower": lower, "rows": len(bucket), "confidence": confidence, "empirical": empirical})
    ordered = sorted(pairs, key=lambda item: item[1], reverse=True)
    positives = sum(actual for actual, _ in ordered)
    tp = 0.0
    pr = []
    for index, (actual, probability) in enumerate(ordered, start=1):
        tp += actual
        if index == len(ordered) or ordered[index][1] != probability:
            pr.append({"threshold": probability, "precision": tp / index, "recall": tp / positives if positives else 0.0})
    return {"rows": len(pairs), "brier": brier, "ece": ece, "bins": bins, "pr_curve": pr}


def _predict(weights: Sequence[float], values: Sequence[float]) -> float:
    return _sigmoid(weights[0] + sum(weight * value for weight, value in zip(weights[1:], values, strict=True)))


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-min(value, 60.0))
        return 1.0 / (1.0 + z)
    z = math.exp(max(value, -60.0))
    return z / (1.0 + z)


def _logit(value: float) -> float:
    bounded = min(1 - 1e-8, max(1e-8, value))
    return math.log(bounded / (1 - bounded))


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(percentile / 100 * len(ordered)) - 1))]


def _markdown(report: Mapping[str, Any]) -> str:
    decision = report["decision"]
    metrics = report["validation"]
    lines = [
        "# E2B Regression V2 Calibration",
        "",
        f"- nominated: `{decision['nominated']}`",
        f"- default enabled: `{decision['default_enabled']}`",
        f"- train / validation: `{report['rows']['train']} / {report['rows']['validation']}`",
        f"- invalid FunctionGemma fallback rows: `{report['rows']['invalid_remote_fallback']}`",
        f"- deterministic validation releases: `{metrics['deterministic_releases']}`",
        f"- E2B proof-gated validation releases: `{metrics['e2b_releases']}`",
        f"- E2B precision: `{metrics['e2b_release_precision']:.2%}`",
        f"- E2B Wilson lower 95%: `{metrics['e2b_release_wilson_lower_95']:.2%}`",
        f"- local coverage: `{metrics['local_coverage']:.2%}`",
        "",
        "## Gates",
        "",
    ]
    lines.extend(f"- [{'x' if passed else ' '}] `{name}`" for name, passed in decision["gates"].items())
    lines.extend([
        "",
        "## Decision",
        "",
        decision["reason"],
        "The final holdout was not opened. Any invalid FunctionGemma assessment routes directly to Fireworks. Probability and expected utility cannot bypass Answer Contract or registered-verifier failure.",
        "",
    ])
    return "\n".join(lines)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
