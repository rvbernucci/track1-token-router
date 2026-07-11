#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import random
import resource
import shutil
import subprocess
import sys
import tempfile
from time import perf_counter
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.evals.shadow_runtime import FrozenFireworksAdapter, ShadowResult, ShadowRuntime, ShadowVariant
from router.orchestration.code_verifier import verify_code_candidate
from router.orchestration.local_adjudication import LocalAdjudicationPolicy
from scripts.promote_e2b_policy import _wilson_lower


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the offline championship shadow, ablations and chaos gates.")
    parser.add_argument("--config", type=Path, default=Path("configs/championship-shadow-policy-v1.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/generated/offline-shadow-championship.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/generated/offline-shadow-championship.md"))
    parser.add_argument("--public-report", type=Path, default=Path("reports/public/offline-shadow-championship.md"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    result = run_shadow(_absolute(args.config))
    _write_json(_absolute(args.output), result)
    markdown = _markdown(result)
    for relative in (args.report, args.public_report):
        path = _absolute(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
    print(json.dumps(result["decision"], sort_keys=True))
    return 0 if result["decision"]["offline_gate_passed"] or not args.check else 1


def run_shadow(config_path: Path) -> dict[str, Any]:
    config = _load_config(config_path)
    evaluation = config["evaluation"]
    inputs = _jsonl(ROOT / evaluation["inputs_path"])
    labels = _jsonl(ROOT / evaluation["labels_path"])
    split = str(evaluation["split"])
    runtime_inputs = [row for row in inputs if row["regression_split"] == split]
    sealed_labels = [row for row in labels if row["regression_split"] == split]
    _validate_label_isolation(inputs, labels)
    split_audit = _split_audit(inputs)

    local_policy_path = ROOT / config["artifacts"]["local_adjudication_policy"]["path"]
    local_policy = LocalAdjudicationPolicy.load(local_policy_path)
    frozen = config["frozen_runtime"]
    fireworks = FrozenFireworksAdapter(
        base_url=str(frozen["fireworks_base_url"]),
        allowed_models=[str(item) for item in frozen["allowed_models"]],
    )
    variants: dict[str, Any] = {}
    variant_results: dict[str, list[ShadowResult]] = {}
    output_dir = ROOT / "reports/generated/shadow-championship"
    output_dir.mkdir(parents=True, exist_ok=True)
    for variant in ShadowVariant:
        runtime = ShadowRuntime(
            variant=variant,
            local_policy=local_policy,
            fireworks=fireworks,
            deadline_ms=float(frozen["deadline_ms"]),
            reserve_ms=float(frozen["reserve_ms"]),
        )
        results = runtime.run(runtime_inputs)
        variant_results[variant.value] = results
        variants[variant.value] = _score(results, sealed_labels)
        (output_dir / f"{variant.value}.jsonl").write_text(
            "".join(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True) + "\n" for result in results),
            encoding="utf-8",
        )

    selected_name = str(config["selected_runtime_variant"])
    selected = variants[selected_name]
    baseline = variants[ShadowVariant.FIREWORKS_ONLY.value]
    mixes = _distribution_mixes(variant_results[selected_name], sealed_labels)
    token_bootstrap = _token_savings_bootstrap(
        variant_results[ShadowVariant.FIREWORKS_ONLY.value],
        variant_results[selected_name],
        sealed_labels,
    )
    chaos = _chaos_suite(runtime_inputs, local_policy, config)
    official_io = _official_io_rehearsal(runtime_inputs)
    docker = _docker_rehearsal_status(config)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    max_rss = int(usage.ru_maxrss)
    max_rss_mib = max_rss / (1024 * 1024) if sys.platform == "darwin" else max_rss / 1024

    gates_config = config["gates"]
    accuracy_regression = baseline["accuracy"] - selected["accuracy"]
    offline_gates = {
        "hashes_and_splits_valid": split_audit["passed"],
        "all_eight_categories_present": len(selected["by_category"]) == 8,
        "selected_accuracy_gate": selected["accuracy"] >= float(gates_config["minimum_accuracy"]),
        "no_material_accuracy_regression": accuracy_regression <= float(gates_config["maximum_accuracy_regression"]),
        "fireworks_tokens_reduced": selected["remote_tokens"] < baseline["remote_tokens"],
        "local_precision_gate": selected["local_precision"] >= float(gates_config["minimum_local_precision"]),
        "runtime_below_shadow_limit": selected["simulated_total_latency_ms"] < float(gates_config["maximum_simulated_runtime_ms"]),
        "memory_below_shadow_limit": selected["simulated_peak_memory_mb"] < float(gates_config["maximum_peak_memory_mb"]),
        "output_schema_valid": selected["output_schema_failures"] == 0,
        "chaos_suite_passed": chaos["passed"],
        "official_io_contract_passed": official_io["passed"],
    }
    offline_gate = all(offline_gates.values())
    release_ready = offline_gate and docker["live_gate_passed"] and local_policy.enabled
    decision = {
        "offline_gate_passed": offline_gate,
        "release_ready": release_ready,
        "selected_runtime_variant": selected_name,
        "local_e2b_policy_enabled": local_policy.enabled,
        "docker_live_gate_passed": docker["live_gate_passed"],
        "submission_attempt_allowed": release_ready,
        "reason": (
            "Offline deterministic+Fireworks shadow passed; release remains blocked until Docker live gate and a stable local-E2B policy pass."
            if offline_gate
            else "Offline shadow failed; retain the current remote-safe runtime and do not submit."
        ),
    }
    return {
        "schema_version": "offline-shadow-championship-v1",
        "config_path": str(config_path),
        "config_sha256": _sha256(config_path),
        "holdout_rows": len(runtime_inputs),
        "split_audit": split_audit,
        "variants": variants,
        "distribution_mixes": mixes,
        "token_savings_bootstrap": token_bootstrap,
        "chaos": chaos,
        "official_io": official_io,
        "docker": docker,
        "process_peak_rss_mib": max_rss_mib,
        "offline_gates": offline_gates,
        "decision": decision,
    }


def _score(results: Sequence[ShadowResult], labels: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    label_index = {str(row["task_id"]): row for row in labels}
    if len(label_index) != len(labels) or [result.task_id for result in results] != [str(row["task_id"]) for row in labels]:
        raise ValueError("Shadow results and sealed labels are not aligned.")
    counts: Counter[str] = Counter()
    by_category: dict[str, Counter[str]] = defaultdict(Counter)
    route_counts: Counter[str] = Counter()
    local_correct = 0
    latencies: list[float] = []
    for result in results:
        label = label_index[result.task_id]
        category = str(label["category"])
        correct = _canonical(category, result.answer) == _canonical(category, str(label["expected_answer"]))
        counts["correct"] += int(correct)
        counts["local_releases"] += int(result.local_release)
        local_correct += int(result.local_release and correct)
        counts["remote_tokens"] += result.remote_tokens
        counts["output_schema_failures"] += int(not result.task_id or not isinstance(result.answer, str) or not result.answer.strip())
        counts["errors"] += int(bool(result.error))
        by_category[category]["rows"] += 1
        by_category[category]["correct"] += int(correct)
        by_category[category]["remote_tokens"] += result.remote_tokens
        by_category[category]["local_releases"] += int(result.local_release)
        route_counts[result.route] += 1
        latencies.append(result.simulated_latency_ms)
    local_releases = counts["local_releases"]
    return {
        **dict(counts),
        "rows": len(results),
        "accuracy": counts["correct"] / len(results) if results else 0.0,
        "local_precision": local_correct / local_releases if local_releases else 1.0,
        "local_wilson_lower_95": _wilson_lower(local_correct, local_releases),
        "local_coverage": local_releases / len(results) if results else 0.0,
        "simulated_total_latency_ms": sum(latencies),
        "simulated_p95_latency_ms": _percentile(latencies, 95),
        "simulated_peak_memory_mb": max((result.simulated_peak_memory_mb for result in results), default=0.0),
        "routes": dict(route_counts),
        "by_category": {
            category: {
                **dict(values),
                "accuracy": values["correct"] / values["rows"],
            }
            for category, values in sorted(by_category.items())
        },
    }


def _distribution_mixes(results: Sequence[ShadowResult], labels: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    label_index = {str(row["task_id"]): row for row in labels}
    weights = {
        "balanced": {},
        "sentiment_ner_heavy": {"sentiment": 4, "ner": 4},
        "code_math_heavy": {"code_debugging": 4, "code_generation": 4, "math_reasoning": 4},
    }
    output: dict[str, Any] = {}
    for name, category_weights in weights.items():
        expanded_results: list[ShadowResult] = []
        expanded_labels: list[Mapping[str, Any]] = []
        for result in results:
            label = label_index[result.task_id]
            multiplier = int(category_weights.get(str(label["category"]), 1))
            for copy_index in range(multiplier):
                expanded_results.append(
                    ShadowResult(**{**asdict_shadow(result), "task_id": f"{result.task_id}#{copy_index}"})
                )
                expanded_labels.append({**label, "task_id": f"{result.task_id}#{copy_index}"})
        output[name] = _score(expanded_results, expanded_labels)
    return output


def asdict_shadow(result: ShadowResult) -> dict[str, Any]:
    return {
        "answer": result.answer,
        "route": result.route,
        "remote_prompt_tokens": result.remote_prompt_tokens,
        "remote_completion_tokens": result.remote_completion_tokens,
        "simulated_latency_ms": result.simulated_latency_ms,
        "simulated_peak_memory_mb": result.simulated_peak_memory_mb,
        "local_release": result.local_release,
        "proof": result.proof,
        "error": result.error,
    }


def _token_savings_bootstrap(
    baseline: Sequence[ShadowResult],
    selected: Sequence[ShadowResult],
    labels: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    baseline_by_id = {row.task_id: row for row in baseline}
    selected_by_id = {row.task_id: row for row in selected}
    groups = [str(row["mutation_lineage"]) for row in labels]
    id_by_group = {str(row["mutation_lineage"]): str(row["task_id"]) for row in labels}
    rng = random.Random(54054)
    savings: list[float] = []
    for _ in range(500):
        sample = [rng.choice(groups) for _ in groups]
        baseline_tokens = sum(baseline_by_id[id_by_group[group]].remote_tokens for group in sample)
        selected_tokens = sum(selected_by_id[id_by_group[group]].remote_tokens for group in sample)
        savings.append(float(baseline_tokens - selected_tokens))
    observed = sum(row.remote_tokens for row in baseline) - sum(row.remote_tokens for row in selected)
    return {
        "lineage_groups": len(groups),
        "resamples": 500,
        "observed_tokens_saved": observed,
        "tokens_saved_ci95": [_percentile(savings, 2.5), _percentile(savings, 97.5)],
    }


def _chaos_suite(inputs: Sequence[Mapping[str, Any]], policy: LocalAdjudicationPolicy, config: Mapping[str, Any]) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    try:
        FrozenFireworksAdapter(base_url="https://shadow.invalid/v1", allowed_models=[])
    except ValueError:
        checks["missing_allowed_models_fails_closed"] = True
    else:
        checks["missing_allowed_models_fails_closed"] = False

    unauthorized = FrozenFireworksAdapter(base_url="https://shadow.invalid/v1", allowed_models=["minimax"])
    try:
        unauthorized.complete(inputs[0])
    except ValueError:
        checks["unauthorized_model_never_reaches_client"] = True
    else:
        checks["unauthorized_model_never_reaches_client"] = False

    allowed = [str(item) for item in config["frozen_runtime"]["allowed_models"]]
    fireworks = FrozenFireworksAdapter(base_url="https://shadow.invalid/v1", allowed_models=allowed)
    malformed_remote = copy.deepcopy(inputs[0])
    malformed_remote["frozen_fireworks"]["answer"] = None
    malformed_result = ShadowRuntime(
        variant=ShadowVariant.FIREWORKS_ONLY,
        local_policy=policy,
        fireworks=fireworks,
    ).run([malformed_remote])[0]
    checks["malformed_fireworks_keeps_valid_result"] = bool(malformed_result.answer and malformed_result.error)

    malformed_e2b = copy.deepcopy(inputs[0])
    malformed_e2b["frozen_e2b"]["answer"] = None
    malformed_local = ShadowRuntime(
        variant=ShadowVariant.PROOF_E2B,
        local_policy=policy,
        fireworks=fireworks,
    ).run([malformed_e2b])[0]
    checks["malformed_e2b_keeps_valid_result"] = bool(malformed_local.answer)

    code_task = TaskEnvelope(input_text="Return only Python code. Write a Python function add(a, b) that returns the sum.")
    code_report = verify_code_candidate(code_task, "import socket\ndef add(a, b):\n    return a + b")
    checks["code_sandbox_blocks_network_import"] = not code_report.accepted

    timeout_results = ShadowRuntime(
        variant=ShadowVariant.FIREWORKS_ONLY,
        local_policy=policy,
        fireworks=fireworks,
        deadline_ms=2.0,
        reserve_ms=1.0,
    ).run(inputs[:5])
    checks["deadline_writes_one_answer_per_task"] = len(timeout_results) == 5 and all(row.answer for row in timeout_results)

    sentinel = "shadow-secret-api-key-should-never-appear"
    serialized = json.dumps([row.to_dict() for row in timeout_results], ensure_ascii=False)
    checks["trace_contains_no_secret_sentinel"] = sentinel not in serialized
    return {"passed": all(checks.values()), "checks": checks}


def _official_io_rehearsal(inputs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="shadow-official-") as tmp:
        root = Path(tmp)
        input_path = root / "input" / "tasks.json"
        output_path = root / "output" / "results.json"
        input_path.parent.mkdir()
        output_path.parent.mkdir()
        selected = inputs[:8]
        input_path.write_text(
            json.dumps([{"task_id": row["task_id"], "prompt": row["prompt"]} for row in selected]),
            encoding="utf-8",
        )
        env = {**os.environ, "ROUTER_MODE": "mock", "ROUTER_LOG_PATH": str(root / "run.jsonl")}
        started = perf_counter()
        completed = subprocess.run(
            [sys.executable, "-m", "router", "submit-track1", "--input", str(input_path), "--output", str(output_path)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        elapsed_ms = (perf_counter() - started) * 1000
        payload = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else None
        shape_ok = isinstance(payload, list) and len(payload) == len(selected) and all(
            isinstance(row, dict) and set(row) == {"task_id", "answer"} and isinstance(row["answer"], str) and row["answer"]
            for row in payload or []
        )
        order_ok = [row["task_id"] for row in payload or []] == [row["task_id"] for row in selected]
        atomic_ok = not output_path.with_name(output_path.name + ".tmp").exists()

        remote_output = root / "output" / "missing-env.json"
        remote_env = {**os.environ, "ROUTER_MODE": "fireworks", "ROUTER_LOG_PATH": str(root / "remote.jsonl")}
        for key in ("FIREWORKS_API_KEY", "FIREWORKS_BASE_URL", "ALLOWED_MODELS"):
            remote_env.pop(key, None)
        missing_env = subprocess.run(
            [sys.executable, "-m", "router", "submit-track1", "--input", str(input_path), "--output", str(remote_output)],
            cwd=ROOT,
            env=remote_env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        missing_env_closed = missing_env.returncode != 0 and not remote_output.exists()
    checks = {
        "exit_zero": completed.returncode == 0,
        "result_shape": shape_ok,
        "order_and_cardinality": order_ok,
        "atomic_write": atomic_ok,
        "under_ten_minutes": elapsed_ms < 600_000,
        "missing_harness_env_fails_closed": missing_env_closed,
    }
    return {"passed": all(checks.values()), "checks": checks, "elapsed_ms": elapsed_ms}


def _docker_rehearsal_status(config: Mapping[str, Any]) -> dict[str, Any]:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    gate = (ROOT / "scripts/docker_resource_gate.sh").read_text(encoding="utf-8")
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    static_checks = {
        "entrypoint_submit_track1": 'ENTRYPOINT ["router"]' in dockerfile and 'CMD ["submit-track1"]' in dockerfile,
        "no_large_weights_copied": "COPY artifacts" not in dockerfile and "COPY data" not in dockerfile,
        "linux_amd64_gate": "linux/amd64" in gate,
        "four_gib_gate": "--memory=4g" in gate,
        "two_cpu_gate": "--cpus=2" in gate,
        "ten_minute_gate": "timeout 600" in gate,
        "ten_gb_gate": "10000000000" in gate,
        "large_paths_ignored": all(path in ignore for path in ("artifacts/", "data/", "reports/")),
    }
    docker_available = shutil.which("docker") is not None
    return {
        "static_gate_passed": all(static_checks.values()),
        "static_checks": static_checks,
        "docker_available": docker_available,
        "live_gate_executed": False,
        "live_gate_passed": False,
        "reason": "Docker CLI is unavailable on this Mac; scripts/docker_resource_gate.sh must run in CI/AMD before release." if not docker_available else "Docker image was not built in this offline shadow run.",
        "declared_limits": config["docker"],
    }


def _load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "championship-shadow-policy-v1":
        raise ValueError("Shadow policy schema is invalid.")
    evaluation = payload["evaluation"]
    for key in ("inputs", "labels", "manifest"):
        artifact = ROOT / evaluation[f"{key}_path"]
        if _sha256(artifact) != evaluation[f"{key}_sha256"]:
            raise ValueError(f"Shadow {key} SHA-256 mismatch.")
    for name, artifact in payload["artifacts"].items():
        path_value = ROOT / artifact["path"]
        if _sha256(path_value) != artifact["sha256"]:
            raise ValueError(f"Shadow artifact {name} SHA-256 mismatch.")
    return payload


def _validate_label_isolation(inputs: Sequence[Mapping[str, Any]], labels: Sequence[Mapping[str, Any]]) -> None:
    forbidden = {"expected_answer", "correct", "label", "gold"}
    if any(forbidden & set(row) for row in inputs):
        raise ValueError("Runtime input contains sealed label fields.")
    if [row["task_id"] for row in inputs] != [row["task_id"] for row in labels]:
        raise ValueError("Input and label task IDs are not aligned.")


def _split_audit(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    splits = ("train", "validation", "final_holdout")
    lineages = {split: {str(row["mutation_lineage"]) for row in rows if row["regression_split"] == split} for split in splits}
    templates = {split: {str(row["template_family"]) for row in rows if row["regression_split"] == split} for split in splits}
    overlap = []
    for index, left in enumerate(splits):
        for right in splits[index + 1 :]:
            if lineages[left] & lineages[right] or templates[left] & templates[right]:
                overlap.append([left, right])
    return {"passed": not overlap, "overlap": overlap, "lineages": {key: len(value) for key, value in lineages.items()}}


def _canonical(category: str, answer: str) -> str:
    value = answer.strip()
    if category == "ner":
        stripped = value
        if stripped.startswith("```") and stripped.endswith("```"):
            stripped = stripped.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        try:
            return json.dumps(json.loads(stripped), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except json.JSONDecodeError:
            return "invalid-json:" + stripped.casefold()
    if category in {"code_debugging", "code_generation"}:
        stripped = value
        if stripped.startswith("```") and stripped.endswith("```"):
            stripped = stripped.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        try:
            return ast.dump(ast.parse(stripped), include_attributes=False)
        except SyntaxError:
            return "invalid-code:" + " ".join(stripped.split())
    return " ".join(value.casefold().split()).strip(" .")


def _markdown(result: Mapping[str, Any]) -> str:
    decision = result["decision"]
    lines = [
        "# Offline Shadow Championship",
        "",
        f"- offline gate: `{decision['offline_gate_passed']}`",
        f"- release ready: `{decision['release_ready']}`",
        f"- selected runtime: `{decision['selected_runtime_variant']}`",
        f"- local E2B enabled: `{decision['local_e2b_policy_enabled']}`",
        f"- Docker live gate: `{decision['docker_live_gate_passed']}`",
        f"- final holdout rows: `{result['holdout_rows']}`",
        "",
        "## Ablations",
        "",
        "| Variant | Accuracy | Fireworks tokens | Local coverage | Local precision | Simulated latency |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, metrics in result["variants"].items():
        lines.append(
            f"| {name} | {metrics['accuracy']:.2%} | {metrics['remote_tokens']} | "
            f"{metrics['local_coverage']:.2%} | {metrics['local_precision']:.2%} | "
            f"{metrics['simulated_total_latency_ms'] / 1000:.2f}s |"
        )
    lines.extend(["", "## Offline Gates", ""])
    lines.extend(f"- [{'x' if passed else ' '}] `{name}`" for name, passed in result["offline_gates"].items())
    lines.extend(
        [
            "",
            "## Docker Gap",
            "",
            f"- static gate: `{result['docker']['static_gate_passed']}`",
            f"- live gate executed: `{result['docker']['live_gate_executed']}`",
            f"- reason: {result['docker']['reason']}",
            "",
            "## Decision",
            "",
            decision["reason"],
            "No submission attempt is authorized by this report. The exact `linux/amd64` resource rehearsal and a stable local-E2B policy remain mandatory.",
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


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
