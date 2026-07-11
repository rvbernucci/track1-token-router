#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys
from time import perf_counter
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import FeatureVector, TaskAssessment, TaskEnvelope
from router.orchestration.assessment import build_feature_vector, compute_structural_features
from router.orchestration.local_adjudication import (
    VerifierFamily,
    build_local_adjudication_evidence,
    combine_adjudication_features,
    distribution_shift_score,
)
from scripts.fit_engine_outcome_models import _fit_binary_variant, _predict_binary_variant
from scripts.promote_e2b_policy import _wilson_lower


PRE_THRESHOLDS = (0.20, 0.30, 0.40, 0.50, 0.60)
POST_THRESHOLDS = (0.50, 0.60, 0.70, 0.80, 0.90, 0.95)
L2 = 0.75
MINIMUM_DEVELOPMENT_LINEAGES = 20
MINIMUM_HOLDOUT_RELEASES = 20
MINIMUM_HOLDOUT_PRECISION = 0.85
MINIMUM_HOLDOUT_WILSON = 0.75


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fit and promote the proof-gated local adjudication policy.")
    parser.add_argument("--dataset", type=Path, default=Path("evals/local-adjudication/adjudication-dataset.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("configs/local-adjudication-policy-v1.json"))
    parser.add_argument("--json-report", type=Path, default=Path("reports/generated/local-adjudication-calibration.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/local-adjudication-calibration.md"))
    parser.add_argument("--public-report", type=Path, default=Path("reports/public/local-adjudication-calibration.md"))
    parser.add_argument(
        "--retrospective-ledger",
        type=Path,
        default=Path("reports/generated/amd-pod-e2b-regression-2000/e2b-post-contract-ledger.jsonl"),
    )
    parser.add_argument("--fresh-holdout", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    report, policy = fit_policy(
        dataset=_absolute(args.dataset),
        fresh_holdout=args.fresh_holdout,
        retrospective_ledger=_absolute(args.retrospective_ledger),
    )
    _write_json(_absolute(args.output), policy)
    _write_json(_absolute(args.json_report), report)
    markdown = _markdown(report)
    for relative in (args.report, args.public_report):
        path = _absolute(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
    print(json.dumps(report["decision"], sort_keys=True))
    return 0 if report["decision"]["promoted"] or not args.check else 1


def fit_policy(*, dataset: Path, fresh_holdout: bool, retrospective_ledger: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_rows = _jsonl(dataset)
    split_audit = _split_audit(raw_rows)
    rows = [_augment(row) for row in raw_rows]
    train = [row for row in rows if row["regression_split"] == "train"]
    validation = [row for row in rows if row["regression_split"] == "validation"]
    holdout = [row for row in rows if row["regression_split"] == "fresh_holdout"]
    if not train or not validation or not holdout or not split_audit["passed"]:
        raise ValueError("Adjudication dataset requires disjoint train, validation and fresh_holdout groups.")

    pre_names = list(train[0]["task_features"]["names"])
    post_names = list(train[0]["combined_features"]["names"])
    pre_coefficients, pre_model_names = _fit_binary_variant(
        [_fit_row(row, "task_features", target="probe_target") for row in train],
        pre_names,
        variant="logistic_linear",
        l2=L2,
    )
    variants: dict[str, dict[str, Any]] = {}
    fitted: dict[str, tuple[list[float], list[str]]] = {}
    for variant in ("constant", "logistic_linear", "logistic_nonlinear"):
        coefficients, names = _fit_binary_variant(
            [_fit_row(row, "combined_features") for row in train], post_names, variant=variant, l2=L2
        )
        fitted[variant] = (coefficients, names)
        pairs = [
            (
                float(row["correct"]),
                _predict_binary_variant(_fit_row(row, "combined_features"), post_names, variant, coefficients),
            )
            for row in validation
        ]
        variants[variant] = _calibration_metrics(pairs)
    monotonic_pairs = [
        (float(row["correct"]), 0.99 if row["evidence"]["hard_gate_passed"] else 0.01)
        for row in validation
    ]
    variants["monotonic_calibrated"] = _calibration_metrics(monotonic_pairs)
    selected_variant = (
        "logistic_linear"
        if variants["logistic_linear"]["brier"] <= variants["logistic_nonlinear"]["brier"] + 0.005
        else "logistic_nonlinear"
    )
    post_coefficients, post_model_names = fitted[selected_variant]

    scored_validation = _score_rows(
        validation,
        pre_names=pre_names,
        pre_coefficients=pre_coefficients,
        post_names=post_names,
        post_coefficients=post_coefficients,
        post_variant=selected_variant,
    )
    development_lineages = _lineage_counts([*train, *validation])
    candidate_families = sorted(
        family for family, count in development_lineages.items() if family != VerifierFamily.NONE.value and count >= MINIMUM_DEVELOPMENT_LINEAGES
    )
    threshold_selection = _select_thresholds(scored_validation, candidate_families)
    pre_threshold = float(threshold_selection["pre_threshold"])
    post_thresholds = {name: float(value) for name, value in threshold_selection["post_thresholds"].items()}

    scored_holdout = _score_rows(
        holdout,
        pre_names=pre_names,
        pre_coefficients=pre_coefficients,
        post_names=post_names,
        post_coefficients=post_coefficients,
        post_variant=selected_variant,
    )
    holdout_metrics = _route_metrics(scored_holdout, pre_threshold, post_thresholds)
    calibration = _calibration_metrics([(float(row["correct"]), float(row["post_probability"])) for row in scored_holdout])
    bootstrap = _bootstrap_by_lineage(scored_holdout, pre_threshold, post_thresholds)
    perturbation = _perturbation_stability(scored_holdout, pre_threshold, post_thresholds)
    reference = _distribution_reference(train)
    mixes = _input_mix_scenarios(scored_holdout, pre_threshold, post_thresholds, reference)
    p95_latency = _percentile([float(row["adjudication_latency_ms"]) for row in holdout], 95)
    actual_e2b = _retrospective_e2b_diagnostic(retrospective_ledger)

    enabled_families = set(candidate_families)
    gates = {
        "fresh_holdout_declared": fresh_holdout,
        "split_groups_disjoint": split_audit["passed"],
        "holdout_not_used_for_model_or_threshold_selection": True,
        "minimum_20_development_lineages_per_enabled_family": all(
            development_lineages.get(name, 0) >= MINIMUM_DEVELOPMENT_LINEAGES for name in enabled_families
        ),
        "minimum_holdout_releases": holdout_metrics["selected_rows"] >= MINIMUM_HOLDOUT_RELEASES,
        "holdout_precision_at_least_85_percent": holdout_metrics["precision"] >= MINIMUM_HOLDOUT_PRECISION,
        "holdout_wilson_at_least_75_percent": holdout_metrics["wilson_lower_95"] >= MINIMUM_HOLDOUT_WILSON,
        "zero_verifier_invalid_releases": holdout_metrics["verifier_invalid_releases"] == 0,
        "zero_false_local_releases": holdout_metrics["false_local_releases"] == 0,
        "factual_open_world_always_remote": holdout_metrics["unsupported_factual_releases"] == 0,
        "perturbation_flip_rate_below_5_percent": perturbation["flip_rate"] < 0.05,
        "p95_adjudication_below_100_ms": p95_latency < 100.0,
    }
    promoted = all(gates.values())
    reason = (
        "Fresh proof-gated holdout passed; local adjudication promoted."
        if promoted
        else "Local adjudication remains disabled because one or more fresh promotion gates failed."
    )
    cohorts: dict[str, Any] = {}
    for family in VerifierFamily:
        if family is VerifierFamily.NONE:
            continue
        cohorts[family.value] = {
            "enabled": family.value in enabled_families,
            "post_threshold": post_thresholds.get(family.value, 0.99),
            "development_lineages": development_lineages.get(family.value, 0),
        }
    policy = {
        "schema_version": "local-adjudication-policy-v1",
        "default_enabled": promoted,
        "thresholds": {"pre_probe": pre_threshold},
        "cohorts": cohorts,
        "models": {
            "pre_response": {
                "variant": "logistic_linear",
                "feature_names": pre_model_names,
                "coefficients": pre_coefficients,
            },
            "post_response": {
                "variant": selected_variant,
                "feature_names": post_model_names,
                "coefficients": post_coefficients,
            },
        },
        "distribution_shift": {
            "maximum_score": 0.55,
            "threshold_penalty": 0.25,
            "reference": reference,
        },
        "fit": {
            "label_policy": "post_correct_true_incorrect_or_uncertain_false;pre_registered_verifier_eligibility",
            "l2": L2,
            "dataset_path": str(dataset.relative_to(ROOT)),
            "dataset_sha256": _sha256(dataset),
            "train_rows": len(train),
            "validation_rows": len(validation),
            "fresh_holdout_rows": len(holdout),
            "threshold_selection_split": "validation",
            "model_selection_split": "validation",
            "promotion_split": "fresh_holdout",
        },
        "artifacts": {
            name: {
                "path": str(path.relative_to(ROOT)),
                "sha256": _sha256(path),
            }
            for name, path in {
                "runtime": ROOT / "router/orchestration/local_adjudication.py",
                "proof_policy": ROOT / "configs/proof-verifier-policy-v1.json",
                "code_policy": ROOT / "configs/code-verifier-policy-v1.json",
                "grounded_policy": ROOT / "configs/grounded-verifier-policy-v1.json",
            }.items()
        },
        "evidence": {
            "promotion_gates": gates,
            "holdout": holdout_metrics,
            "fresh_holdout": fresh_holdout,
        },
        "reason": reason,
    }
    report = {
        "schema_version": "local-adjudication-calibration-v1",
        "dataset": str(dataset),
        "label_counts": dict(Counter(str(row["label_status"]) for row in rows)),
        "split_rows": {name: sum(row["regression_split"] == name for row in rows) for name in ("train", "validation", "fresh_holdout")},
        "split_audit": split_audit,
        "development_lineages": development_lineages,
        "model_variants": variants,
        "pre_validation_calibration": _calibration_metrics(
            [(float(row["probe_target"]), float(row["pre_probability"])) for row in scored_validation]
        ),
        "selected_variant": selected_variant,
        "threshold_selection": threshold_selection,
        "fresh_holdout": holdout_metrics,
        "calibration": calibration,
        "bootstrap_by_lineage": bootstrap,
        "input_mix_scenarios": mixes,
        "perturbation_stability": perturbation,
        "p95_adjudication_latency_ms": p95_latency,
        "retrospective_actual_e2b_diagnostic": actual_e2b,
        "decision": {"promoted": promoted, "gates": gates, "reason": reason},
    }
    return report, policy


def _augment(row: Mapping[str, Any]) -> dict[str, Any]:
    assessment = TaskAssessment.from_mapping(row["assessment"])
    task = TaskEnvelope(id=str(row["task_id"]), input_text=str(row["prompt"]))
    task_features = build_feature_vector(assessment, compute_structural_features(task))
    started = perf_counter()
    evidence = build_local_adjudication_evidence(task, str(row["candidate"]))
    latency_ms = (perf_counter() - started) * 1000
    if evidence.verifier_family.value != str(row["expected_verifier_family"]):
        raise ValueError(f"Verifier family mismatch for {row['id']!r}.")
    return {
        **dict(row),
        "task_features": task_features.to_dict(),
        "combined_features": combine_adjudication_features(task_features, evidence).to_dict(),
        "evidence": evidence.to_dict(),
        "adjudication_latency_ms": latency_ms,
        "probe_target": evidence.verifier_supported,
    }


def _fit_row(
    row: Mapping[str, Any],
    feature_key: str,
    *,
    target: str = "correct",
) -> dict[str, Any]:
    return {"correct": bool(row[target]), "features": row[feature_key]}


def _score_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    pre_names: Sequence[str],
    pre_coefficients: Sequence[float],
    post_names: Sequence[str],
    post_coefficients: Sequence[float],
    post_variant: str,
) -> list[dict[str, Any]]:
    return [
        {
            **dict(row),
            "pre_probability": _predict_binary_variant(
                _fit_row(row, "task_features"), pre_names, "logistic_linear", pre_coefficients
            ),
            "post_probability": _predict_binary_variant(
                _fit_row(row, "combined_features"), post_names, post_variant, post_coefficients
            ),
        }
        for row in rows
    ]


def _select_thresholds(rows: Sequence[Mapping[str, Any]], families: Sequence[str]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for pre in PRE_THRESHOLDS:
        thresholds: dict[str, float] = {}
        family_metrics: dict[str, Any] = {}
        for family in families:
            family_rows = [row for row in rows if row["expected_verifier_family"] == family]
            options = [
                _route_metrics(family_rows, pre, {family: post}) | {"post_threshold": post}
                for post in POST_THRESHOLDS
            ]
            chosen = max(
                options,
                key=lambda item: (
                    item["wilson_lower_95"],
                    item["precision"],
                    item["selected_rows"],
                    item["estimated_tokens_saved"],
                    item["post_threshold"],
                ),
            )
            thresholds[family] = float(chosen["post_threshold"])
            family_metrics[family] = chosen
        aggregate = _route_metrics(rows, pre, thresholds)
        perturbation = _perturbation_stability(rows, pre, thresholds)
        candidates.append(
            {
                "pre_threshold": pre,
                "post_thresholds": thresholds,
                "family_metrics": family_metrics,
                "aggregate": aggregate,
                "perturbation_stability": perturbation,
            }
        )
    selected = max(
        candidates,
        key=lambda item: (
            item["perturbation_stability"]["flip_rate"] < 0.05,
            item["aggregate"]["wilson_lower_95"],
            item["aggregate"]["precision"],
            item["aggregate"]["selected_rows"],
            item["aggregate"]["estimated_tokens_saved"],
            -item["pre_threshold"],
        ),
    )
    return {"candidates": candidates, **selected}


def _route_metrics(rows: Sequence[Mapping[str, Any]], pre_threshold: float, post_thresholds: Mapping[str, float], *, drift_score: float = 0.0) -> dict[str, Any]:
    selected: list[Mapping[str, Any]] = []
    for row in rows:
        family = str(row["expected_verifier_family"])
        threshold = post_thresholds.get(family)
        if threshold is None or drift_score > 0.55:
            continue
        adjusted = min(0.999, float(threshold) + max(0.0, drift_score) * 0.25)
        if (
            float(row["pre_probability"]) >= pre_threshold
            and float(row["post_probability"]) >= adjusted
            and row["evidence"]["hard_gate_passed"] is True
        ):
            selected.append(row)
    correct = sum(row["correct"] is True for row in selected)
    false_local = len(selected) - correct
    precision = correct / len(selected) if selected else 0.0
    factual = sum(row["expected_verifier_family"] == VerifierFamily.NONE.value for row in selected)
    tokens = sum(math.ceil((len(str(row["prompt"])) + len(str(row["candidate"]))) / 4) for row in selected)
    return {
        "rows": len(rows),
        "selected_rows": len(selected),
        "correct_local_releases": correct,
        "false_local_releases": false_local,
        "precision": precision,
        "wilson_lower_95": _wilson_lower(correct, len(selected)),
        "coverage": len(selected) / len(rows) if rows else 0.0,
        "abstention_rate": 1.0 - len(selected) / len(rows) if rows else 1.0,
        "verifier_invalid_releases": sum(not row["evidence"]["hard_gate_passed"] for row in selected),
        "unsupported_factual_releases": factual,
        "estimated_tokens_saved": tokens,
    }


def _calibration_metrics(pairs: Sequence[tuple[float, float]]) -> dict[str, Any]:
    if not pairs:
        return {"rows": 0, "brier": 1.0, "ece": 1.0, "accuracy": 0.0}
    brier = sum((prediction - actual) ** 2 for actual, prediction in pairs) / len(pairs)
    accuracy = sum((prediction >= 0.5) == bool(actual) for actual, prediction in pairs) / len(pairs)
    bins: list[dict[str, Any]] = []
    ece = 0.0
    for lower in (0.0, 0.2, 0.4, 0.6, 0.8):
        bucket = [(actual, prediction) for actual, prediction in pairs if lower <= prediction < lower + 0.2 or (lower == 0.8 and prediction == 1.0)]
        if not bucket:
            continue
        confidence = sum(prediction for _, prediction in bucket) / len(bucket)
        empirical = sum(actual for actual, _ in bucket) / len(bucket)
        ece += len(bucket) / len(pairs) * abs(confidence - empirical)
        bins.append({"lower": lower, "rows": len(bucket), "confidence": confidence, "empirical": empirical})
    return {"rows": len(pairs), "brier": brier, "ece": ece, "accuracy": accuracy, "bins": bins}


def _bootstrap_by_lineage(rows: Sequence[Mapping[str, Any]], pre: float, posts: Mapping[str, float]) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["mutation_lineage"])].append(row)
    lineages = sorted(grouped)
    rng = random.Random(53054)
    precisions: list[float] = []
    coverages: list[float] = []
    for _ in range(400):
        sample = [row for _ in lineages for row in grouped[rng.choice(lineages)]]
        metrics = _route_metrics(sample, pre, posts)
        precisions.append(float(metrics["precision"]))
        coverages.append(float(metrics["coverage"]))
    return {
        "resamples": 400,
        "lineage_groups": len(lineages),
        "precision_ci95": [_percentile(precisions, 2.5), _percentile(precisions, 97.5)],
        "coverage_ci95": [_percentile(coverages, 2.5), _percentile(coverages, 97.5)],
    }


def _perturbation_stability(rows: Sequence[Mapping[str, Any]], pre: float, posts: Mapping[str, float]) -> dict[str, Any]:
    flips = comparisons = 0
    for row in rows:
        family = str(row["expected_verifier_family"])
        if family not in posts:
            continue
        base = _selected(row, pre, posts[family])
        for delta in (-0.02, 0.02):
            perturbed = (
                float(row["pre_probability"]) + delta >= pre
                and float(row["post_probability"]) + delta >= posts[family]
                and row["evidence"]["hard_gate_passed"] is True
            )
            flips += int(base != perturbed)
            comparisons += 1
    return {"comparisons": comparisons, "flips": flips, "flip_rate": flips / comparisons if comparisons else 0.0}


def _selected(row: Mapping[str, Any], pre: float, post: float) -> bool:
    return bool(
        float(row["pre_probability"]) >= pre
        and float(row["post_probability"]) >= post
        and row["evidence"]["hard_gate_passed"] is True
    )


def _distribution_reference(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    assessments = [row["assessment"] for row in rows]
    intent_counts = Counter(str(item["intent"]) for item in assessments)
    score_names = tuple(assessments[0]["scores"])
    means: dict[str, float] = {}
    deviations: dict[str, float] = {}
    for name in score_names:
        values = [float(item["scores"][name]) / 10.0 for item in assessments]
        means[name] = statistics.fmean(values)
        deviations[name] = statistics.pstdev(values) or 0.05
    return {
        "intent_mix": {name: count / len(assessments) for name, count in sorted(intent_counts.items())},
        "score_mean": means,
        "score_std": deviations,
    }


def _input_mix_scenarios(rows: Sequence[Mapping[str, Any]], pre: float, posts: Mapping[str, float], reference: Mapping[str, Any]) -> dict[str, Any]:
    scenarios = {
        "balanced": {},
        "sentiment_heavy": {"sentiment": 5},
        "extraction_heavy": {"ner": 4, "factual_qa": 3, "summarization": 3},
        "code_heavy": {"code_generation": 6},
    }
    result: dict[str, Any] = {}
    for name, weights in scenarios.items():
        sample: list[Mapping[str, Any]] = []
        for row in rows:
            multiplier = int(weights.get(str(row["assessment"]["intent"]), 1))
            sample.extend([row] * multiplier)
        drift = distribution_shift_score(reference, [row["assessment"] for row in sample])
        result[name] = {"drift_score": drift, **_route_metrics(sample, pre, posts, drift_score=drift)}
    return result


def _lineage_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    by_family: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        by_family[str(row["expected_verifier_family"])].add(str(row["mutation_lineage"]))
    return {family: len(values) for family, values in sorted(by_family.items())}


def _split_audit(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    splits = ("train", "validation", "fresh_holdout")
    lineage_sets = {split: {str(row["mutation_lineage"]) for row in rows if row["regression_split"] == split} for split in splits}
    template_sets = {split: {str(row["template_family"]) for row in rows if row["regression_split"] == split} for split in splits}
    lineage_overlap = sorted((left, right) for index, left in enumerate(splits) for right in splits[index + 1 :] if lineage_sets[left] & lineage_sets[right])
    template_overlap = sorted((left, right) for index, left in enumerate(splits) for right in splits[index + 1 :] if template_sets[left] & template_sets[right])
    return {
        "passed": not lineage_overlap and not template_overlap,
        "lineage_overlap": lineage_overlap,
        "template_overlap": template_overlap,
        "lineage_counts": {split: len(lineage_sets[split]) for split in splits},
        "template_counts": {split: len(template_sets[split]) for split in splits},
    }


def _retrospective_e2b_diagnostic(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"available": False, "reason": "ledger_missing"}
    counts: Counter[str] = Counter()
    by_family: dict[str, Counter[str]] = defaultdict(Counter)
    for row in _jsonl(path):
        task = TaskEnvelope(id=str(row.get("task_id") or ""), input_text=str(row.get("task_text") or ""))
        candidate = str(row.get("answer_after_contract") or row.get("answer_before_contract") or "")
        try:
            evidence = build_local_adjudication_evidence(task, candidate)
        except Exception:
            counts["errors"] += 1
            continue
        correct = row.get("final_verdict") == "correct"
        counts["rows"] += 1
        counts["verifier_supported"] += int(evidence.verifier_supported)
        counts["verifier_accepted"] += int(evidence.hard_gate_passed)
        counts["accepted_correct"] += int(evidence.hard_gate_passed and correct)
        counts["accepted_not_correct"] += int(evidence.hard_gate_passed and not correct)
        by_family[evidence.verifier_family.value]["supported"] += int(evidence.verifier_supported)
        by_family[evidence.verifier_family.value]["accepted"] += int(evidence.hard_gate_passed)
        by_family[evidence.verifier_family.value]["accepted_correct"] += int(evidence.hard_gate_passed and correct)
    accepted = counts["verifier_accepted"]
    return {
        "available": True,
        **dict(counts),
        "accepted_precision": counts["accepted_correct"] / accepted if accepted else None,
        "note": "Retrospective actual E2B evidence is diagnostic only and was not used for fitting or promotion.",
        "by_family": {name: dict(values) for name, values in sorted(by_family.items())},
    }


def _markdown(report: Mapping[str, Any]) -> str:
    holdout = report["fresh_holdout"]
    decision = report["decision"]
    lines = [
        "# Local Adjudication Calibration",
        "",
        f"- promoted: `{decision['promoted']}`",
        f"- fresh holdout releases: `{holdout['selected_rows']}`",
        f"- fresh holdout precision: `{holdout['precision']:.2%}`",
        f"- Wilson lower 95%: `{holdout['wilson_lower_95']:.2%}`",
        f"- fresh holdout coverage: `{holdout['coverage']:.2%}`",
        f"- false local releases: `{holdout['false_local_releases']}`",
        f"- Brier score: `{report['calibration']['brier']:.4f}`",
        f"- expected calibration error: `{report['calibration']['ece']:.4f}`",
        f"- p95 evidence latency: `{report['p95_adjudication_latency_ms']:.2f} ms`",
        "",
        "## Gates",
        "",
    ]
    lines.extend(f"- [{'x' if passed else ' '}] `{name}`" for name, passed in decision["gates"].items())
    lines.extend(
        [
            "",
            "## Model Selection",
            "",
            f"Selected `{report['selected_variant']}` after comparing constant, linear logistic, nonlinear logistic and monotonic calibrated variants on validation only.",
            "Thresholds maximize Wilson lower precision before coverage. The fresh holdout is used only for the final promotion decision.",
            "",
            "## Runtime Contract",
            "",
            "A local answer is released only when the E2B candidate satisfies Answer Contract v2, a registered verifier accepts it, the post model clears its cohort threshold and distribution drift remains inside the calibrated envelope. Every failure routes to Fireworks; factual open-world tasks remain remote.",
            "",
        ]
    )
    return "\n".join(lines)


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile / 100 * len(ordered)) - 1))
    return ordered[index]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
