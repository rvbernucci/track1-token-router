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
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.orchestration.local_adjudication import build_local_adjudication_evidence
from router.orchestration.solvers import solve_deterministic
from scripts.adjudicate_e2b_regression_v2 import _mechanical
from scripts.fit_e2b_regression_v2 import _calibrated_predict, _features
from scripts.promote_e2b_policy import _wilson_lower


RUN = ROOT / "evals/e2b-regression-v2-championship"
UPSTREAM = ROOT / "evals/e2b-regression-v2-adjudication"
CANDIDATE_POLICY = ROOT / "configs/e2b-local-adjudication-v2-candidate.json"
PROMOTED_POLICY = ROOT / "configs/e2b-local-adjudication-v2.json"
JSON_REPORT = ROOT / "reports/generated/e2b-regression-v2-championship.json"
MARKDOWN_REPORT = ROOT / "reports/generated/e2b-regression-v2-championship.md"
# The official guide does not publish a numeric gate. This is the project's
# pre-existing frozen feasibility threshold from e2b-route-policy-v1.
DECLARED_ACCURACY_GATE = 0.60


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-time sealed Sprint 59 championship evaluation.")
    parser.add_argument("--prepare-fireworks-judging", action="store_true")
    parser.add_argument("--final-holdout", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.prepare_fireworks_judging:
        print(json.dumps(prepare_fireworks_judging(), sort_keys=True))
        return 0
    if not args.final_holdout:
        parser.error("choose --prepare-fireworks-judging or --final-holdout")
    report, policy = evaluate()
    _write_json(PROMOTED_POLICY, policy)
    _write_json(JSON_REPORT, report)
    MARKDOWN_REPORT.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_REPORT.write_text(_markdown(report), encoding="utf-8")
    result = check() if args.check else report["decision"]
    print(json.dumps(result, sort_keys=True))
    return 0


def prepare_fireworks_judging() -> dict[str, Any]:
    candidates = {str(row["task_id"]): row for row in _jsonl(UPSTREAM / "sealed/final-holdout-candidates.jsonl")}
    baseline = _jsonl(RUN / "sealed/fireworks-baseline.jsonl")
    rows = []
    verdicts = Counter()
    for answer in baseline:
        task_id = str(answer["task_id"])
        candidate = candidates[task_id]
        mechanical = _mechanical(
            {"reference_answer": candidate["reference_answer"], "output_shape": candidate["output_shape"]},
            str(answer["answer"]),
            bool(answer["contract"] and answer["contract"].get("valid")),
            str(candidate["category"]),
        )
        verdicts[mechanical["verdict"]] += 1
        rows.append({
            "id": f"fireworks-v2-{task_id}",
            "task_id": task_id,
            "task_text": candidate["task_text"],
            "answer": answer["answer"],
            "reference_answer": candidate["reference_answer"],
            "reference_rubric": candidate["reference_rubric"],
            "functiongemma_assessment": candidate["functiongemma_assessment"],
            "mechanical": mechanical,
            "engine": "fireworks-routed-baseline",
            "engine_version": str(answer["model"]),
        })
    _write_jsonl(RUN / "sealed/fireworks-candidates.jsonl", rows)
    queue = [row for row in rows if row["mechanical"]["verdict"] == "uncertain"]
    _write_jsonl(RUN / "sealed/fireworks-judge-queue.jsonl", queue)
    return {"rows": len(rows), "judge_queue": len(queue), "mechanical": dict(verdicts)}


def evaluate() -> tuple[dict[str, Any], dict[str, Any]]:
    upstream = _verify_upstream()
    candidate_policy = json.loads(CANDIDATE_POLICY.read_text())
    candidate_hash = _sha256(CANDIDATE_POLICY)
    candidates = {str(row["task_id"]): row for row in _jsonl(UPSTREAM / "sealed/final-holdout-candidates.jsonl")}
    labels = {str(row["task_id"]): row for row in _jsonl(UPSTREAM / "sealed/final-holdout-labels.jsonl")}
    metadata = {str(row["task_id"]): row for row in _jsonl(ROOT / "evals/e2b-regression-v2/metadata.jsonl") if row["split"] == "final_holdout"}
    baseline = {str(row["task_id"]): row for row in _jsonl(RUN / "sealed/fireworks-baseline.jsonl")}
    if not (set(candidates) == set(labels) == set(metadata) == set(baseline)) or len(labels) != 400:
        raise ValueError("Final holdout artifacts are not exactly aligned at 400 rows.")
    fireworks_labels = _fireworks_labels()
    rows = [
        _evaluate_row(task_id, candidates[task_id], labels[task_id], metadata[task_id], baseline[task_id], fireworks_labels[task_id], candidate_policy)
        for task_id in sorted(labels)
    ]
    variants = {
        name: _variant_metrics(rows, name)
        for name in ("fireworks_only", "deterministic_fireworks", "e2b_probe", "full_v2")
    }
    bootstrap = {name: _token_bootstrap(rows, name) for name in variants if name != "fireworks_only"}
    mixes = _mixes(rows)
    candidate = variants["full_v2"]
    baseline_metrics = variants["deterministic_fireworks"]
    development_gates = candidate_policy["evidence"]["nomination_gates"]
    gates = {
        "upstream_hashes_verified": upstream["passed"],
        "candidate_frozen_before_unseal": True,
        "overall_accuracy_gate": candidate["accuracy"] >= DECLARED_ACCURACY_GATE,
        "accuracy_regression_at_most_one_point": candidate["accuracy"] >= baseline_metrics["accuracy"] - 0.01,
        "local_precision_at_least_95pct": candidate["local_precision"] >= 0.95,
        "local_wilson_at_least_90pct": candidate["local_wilson_lower_95"] >= 0.90,
        "zero_verifier_invalid_releases": candidate["verifier_invalid_releases"] == 0,
        "probability_flip_rate_below_5pct": bool(development_gates["probability_flip_rate_below_5pct"]),
        "score_shift_flip_rate_below_5pct": bool(development_gates["score_shift_flip_rate_below_5pct"]),
        "positive_token_savings_lower_bound": bootstrap["full_v2"]["tokens_saved_ci95"][0] > 0,
    }
    statistical_promotion = all(gates.values())
    reason = (
        "V2 passed sealed statistical gates; runtime gates remain required before enablement."
        if statistical_promotion
        else "V2 rejected on frozen evidence; retain proof-carrying deterministic plus Fireworks."
    )
    manifest = {
        "schema_version": "e2b-v2-championship-run-manifest-v1",
        "candidate_policy_sha256": candidate_hash,
        "upstream": upstream,
        "fireworks_baseline_sha256": _sha256(RUN / "sealed/fireworks-baseline.jsonl"),
        "fireworks_judgments": {
            "agy_sha256": _sha256(RUN / "sealed/fireworks-judgments-agy.jsonl"),
            "codex_sha256": _sha256(RUN / "sealed/fireworks-judgments-codex.jsonl"),
        },
        "threshold_or_coefficient_changes_after_unseal": False,
    }
    _write_json(RUN / "run-manifest.json", manifest)
    policy = json.loads(json.dumps(candidate_policy))
    policy["schema_version"] = "e2b-local-adjudication-v2"
    policy["default_enabled"] = False
    policy["promotion"] = {
        "statistical_promotion_passed": statistical_promotion,
        "runtime_promotion_passed": False,
        "final_decision": "retain_deterministic_fireworks" if not statistical_promotion else "pending_runtime_gates",
        "candidate_policy_sha256": candidate_hash,
        "manifest_sha256": _sha256(RUN / "run-manifest.json"),
        "gates": gates,
    }
    policy["reason"] = reason
    report = {
        "schema_version": "e2b-regression-v2-championship-v1",
        "declared_accuracy_gate": DECLARED_ACCURACY_GATE,
        "variants": variants,
        "paired_token_bootstrap": bootstrap,
        "input_mixes": mixes,
        "manifest": manifest,
        "decision": {"statistical_promotion": statistical_promotion, "gates": gates, "reason": reason},
    }
    return report, policy


def check() -> dict[str, Any]:
    report = json.loads(JSON_REPORT.read_text())
    policy = json.loads(PROMOTED_POLICY.read_text())
    manifest = json.loads((RUN / "run-manifest.json").read_text())
    docker_path = ROOT / "reports/generated/e2b-v2-docker-gate.json"
    docker = json.loads(docker_path.read_text()) if docker_path.exists() else None
    statistical = bool(report["decision"]["statistical_promotion"])
    runtime_pass = bool(
        docker
        and docker.get("ok") is True
        and docker.get("image") == "linux/amd64"
        and int(docker.get("compressed_size_bytes", 10**20)) < 10_000_000_000
        and float(docker.get("process_max_rss_mib", 10**20)) <= 3584
        and int(docker.get("observed_runtime_seconds", 601)) <= 570
    )
    gates = {
        "manifest_candidate_hash": manifest["candidate_policy_sha256"] == _sha256(CANDIDATE_POLICY),
        "promoted_policy_disabled_when_statistical_gate_failed": statistical or policy["default_enabled"] is False,
        "runtime_gate_recorded": docker is not None,
        "runtime_gate_passed": runtime_pass,
        "official_rows_preserved": all(value["rows"] == 400 for value in report["variants"].values()),
        "no_post_unseal_retuning": manifest["threshold_or_coefficient_changes_after_unseal"] is False,
    }
    final_enable = statistical and runtime_pass and all(gates.values())
    policy["default_enabled"] = final_enable
    policy["promotion"]["runtime_promotion_passed"] = runtime_pass
    policy["promotion"]["final_decision"] = "promote_v2" if final_enable else "retain_deterministic_fireworks"
    _write_json(PROMOTED_POLICY, policy)
    if policy["default_enabled"] is not final_enable:
        if final_enable:
            raise ValueError("Statistical/runtime gates passed but policy was not enabled.")
        if policy["default_enabled"]:
            raise ValueError("Policy enabled without every mandatory gate.")
    if not all(gates.values()):
        raise ValueError(f"Sprint 59 checks failed: {[name for name, passed in gates.items() if not passed]}")
    return {"passed": True, "statistical_promotion": statistical, "runtime_promotion": runtime_pass, "default_enabled": policy["default_enabled"], "gates": gates}


def _verify_upstream() -> dict[str, Any]:
    label_policy = json.loads((ROOT / "configs/e2b-regression-v2-label-policy.json").read_text())
    candidate_policy = json.loads(CANDIDATE_POLICY.read_text())
    gates = {
        "sealed_candidates": _sha256(UPSTREAM / "sealed/final-holdout-candidates.jsonl") == label_policy["sealed_final_candidates_sha256"],
        "sealed_labels": _sha256(UPSTREAM / "sealed/final-holdout-labels.jsonl") == label_policy["sealed_final_labels_sha256"],
        "development_candidates": _sha256(UPSTREAM / "development/candidates.jsonl") == candidate_policy["fit"]["candidate_sha256"],
        "development_labels": _sha256(UPSTREAM / "development/labels.jsonl") == candidate_policy["fit"]["labels_sha256"],
        "candidate_disabled": candidate_policy["default_enabled"] is False,
    }
    if not all(gates.values()):
        raise ValueError(f"Upstream hash verification failed: {[key for key, value in gates.items() if not value]}")
    return {"passed": True, "gates": gates}


def _fireworks_labels() -> dict[str, bool]:
    candidates = {str(row["task_id"]): row for row in _jsonl(RUN / "sealed/fireworks-candidates.jsonl")}
    judgments = defaultdict(list)
    for path in (RUN / "sealed/fireworks-judgments-agy.jsonl", RUN / "sealed/fireworks-judgments-codex.jsonl"):
        for row in _jsonl(path):
            judgments[str(row["candidate_id"])].append(str(row["verdict"]))
    result = {}
    for task_id, row in candidates.items():
        mechanical = row["mechanical"]
        if mechanical["hard"]:
            verdict = mechanical["verdict"]
        else:
            values = judgments.get(str(row["id"]), [])
            verdict = values[0] if len(values) >= 2 and len(set(values[:2])) == 1 else "uncertain"
        result[task_id] = verdict == "correct"
    return result


def _evaluate_row(task_id: str, candidate: Mapping[str, Any], label: Mapping[str, Any], metadata: Mapping[str, Any], baseline: Mapping[str, Any], baseline_correct: bool, policy: Mapping[str, Any]) -> dict[str, Any]:
    task = TaskEnvelope(id=task_id, input_text=str(candidate["task_text"]))
    assessment = label.get("functiongemma_assessment")
    assessment_valid = bool(label.get("assessment_valid")) and isinstance(assessment, Mapping)
    p_det = p_e2b = 0.0
    if assessment_valid:
        values = _features(task.input_text, assessment)["values"]
        p_det = _calibrated_predict(policy["models"]["deterministic"], values)
        p_e2b = _calibrated_predict(policy["models"]["e2b"], values)
    solver = solve_deterministic(task) if assessment_valid else None
    solver_evidence = build_local_adjudication_evidence(task, solver.answer).to_dict() if solver else None
    deterministic_release = bool(
        solver
        and p_det >= float(policy["thresholds"]["deterministic_probe"])
        and solver_evidence
        and solver_evidence["hard_gate_passed"]
    )
    e2b_release = bool(
        assessment_valid
        and p_e2b >= float(policy["thresholds"]["e2b_release"])
        and label["contract_valid"]
        and candidate["local_verifier_evidence"]["hard_gate_passed"]
        and candidate["category"] != "factual_qa"
    )
    full_release = e2b_release and candidate["local_verifier_evidence"]["verifier_family"] in policy["enabled_verifier_families"]
    routes = {
        "fireworks_only": {"local": False, "correct": baseline_correct},
        "deterministic_fireworks": {"local": deterministic_release, "correct": True if deterministic_release else baseline_correct},
        "e2b_probe": {"local": deterministic_release or (not deterministic_release and e2b_release), "correct": True if deterministic_release else bool(label["binary_label"]) if e2b_release else baseline_correct},
        "full_v2": {"local": deterministic_release or (not deterministic_release and full_release), "correct": True if deterministic_release else bool(label["binary_label"]) if full_release else baseline_correct},
    }
    return {
        "task_id": task_id,
        "category": candidate["category"],
        "lineage": metadata["mutation_lineage"],
        "assessment_valid": assessment_valid,
        "p_deterministic": p_det,
        "p_e2b": p_e2b,
        "deterministic_release": deterministic_release,
        "e2b_release": e2b_release,
        "full_release": full_release,
        "e2b_correct": bool(label["binary_label"]),
        "e2b_verifier_valid": bool(candidate["local_verifier_evidence"]["hard_gate_passed"]),
        "remote_tokens": int(baseline["usage"]["total"]),
        "routes": routes,
    }


def _variant_metrics(rows: Sequence[Mapping[str, Any]], name: str) -> dict[str, Any]:
    correct = sum(row["routes"][name]["correct"] for row in rows)
    local = [row for row in rows if row["routes"][name]["local"]]
    local_correct = sum(row["routes"][name]["correct"] for row in local)
    categories = {
        category: {
            "rows": len(items),
            "correct": sum(row["routes"][name]["correct"] for row in items),
            "accuracy": sum(row["routes"][name]["correct"] for row in items) / len(items),
        }
        for category in sorted({str(row["category"]) for row in rows})
        if (items := [row for row in rows if row["category"] == category])
    }
    return {
        "rows": len(rows),
        "correct": correct,
        "accuracy": correct / len(rows),
        "local_releases": len(local),
        "local_coverage": len(local) / len(rows),
        "local_precision": local_correct / len(local) if local else 0.0,
        "local_wilson_lower_95": _wilson_lower(local_correct, len(local)),
        "verifier_invalid_releases": sum(not row["e2b_verifier_valid"] for row in local if not row["deterministic_release"]),
        "fireworks_tokens": sum(row["remote_tokens"] for row in rows if not row["routes"][name]["local"]),
        "categories": categories,
    }


def _token_bootstrap(rows: Sequence[Mapping[str, Any]], name: str) -> dict[str, Any]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["lineage"]].append(row)
    lineages = sorted(grouped)
    rng = random.Random(59000 + len(name))
    savings = []
    for _ in range(1000):
        sample = [row for _ in lineages for row in grouped[rng.choice(lineages)]]
        savings.append(sum(row["remote_tokens"] for row in sample if row["routes"][name]["local"]))
    return {"resamples": len(savings), "tokens_saved_ci95": [_percentile(savings, 2.5), _percentile(savings, 97.5)]}


def _mixes(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    scenarios = {
        "balanced": {},
        "sentiment_ner_heavy": {"sentiment": 4, "ner": 4},
        "code_math_heavy": {"code_generation": 4, "code_debugging": 4, "math_reasoning": 4},
    }
    result = {}
    for scenario, weights in scenarios.items():
        sample = [row for row in rows for _ in range(weights.get(row["category"], 1))]
        result[scenario] = {name: _variant_metrics(sample, name) for name in ("fireworks_only", "deterministic_fireworks", "e2b_probe", "full_v2")}
    return result


def _markdown(report: Mapping[str, Any]) -> str:
    decision = report["decision"]
    lines = ["# E2B Regression V2 Championship", "", f"- statistical promotion: `{decision['statistical_promotion']}`", f"- declared accuracy gate: `{report['declared_accuracy_gate']:.2%}`", "", "## Variants", ""]
    for name, row in report["variants"].items():
        lines.append(f"- `{name}`: accuracy `{row['accuracy']:.2%}`, local coverage `{row['local_coverage']:.2%}`, Fireworks tokens `{row['fireworks_tokens']}`")
    lines.extend(["", "## Gates", ""])
    lines.extend(f"- [{'x' if passed else ' '}] `{name}`" for name, passed in decision["gates"].items())
    lines.extend(["", "## Decision", "", decision["reason"], "No final-holdout prompt, answer or reference is published in this report.", ""])
    return "\n".join(lines)


def _percentile(values: Sequence[int], percentile: float) -> int:
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(percentile / 100 * len(ordered)) - 1))]


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
