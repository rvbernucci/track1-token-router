#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.adapters.io import load_jsonl_tasks, write_jsonl_results
from router.core.contracts import TaskEnvelope
from router.core.fireworks import FireworksClient
from router.core.hybrid_cascade import HybridCascadeRunner
from router.core.local_runner import LocalM1Runner
from router.core.mock_runner import MockCascadeRunner
from router.core.model_client import LocalModelClient
from router.dev.fake_provider import FakeOpenAIProvider, FakeProviderConfig
from router.evals.operational_envelope import percentile
from router.orchestration.competition import CompetitionRunner


DEFAULT_BATCH_PATH = Path("fixtures/stress/batch-1k.jsonl")
DEFAULT_MIXED_PATH = Path("fixtures/stress/mixed.jsonl")


@dataclass(frozen=True)
class BatchStressThresholds:
    max_batch_elapsed_ms: float = 10_000.0
    max_p95_ms: float = 25.0
    min_tasks_per_second: float = 100.0
    max_uncontrolled_crashes: int = 0

    @classmethod
    def from_env(cls) -> "BatchStressThresholds":
        return cls(
            max_batch_elapsed_ms=_float_env("BATCH_STRESS_MAX_BATCH_MS", cls.max_batch_elapsed_ms),
            max_p95_ms=_float_env("BATCH_STRESS_MAX_P95_MS", cls.max_p95_ms),
            min_tasks_per_second=_float_env("BATCH_STRESS_MIN_TASKS_PER_SECOND", cls.min_tasks_per_second),
            max_uncontrolled_crashes=_int_env("BATCH_STRESS_MAX_UNCONTROLLED_CRASHES", cls.max_uncontrolled_crashes),
        )

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def run_batch_stress(
    *,
    batch_path: Path = DEFAULT_BATCH_PATH,
    mixed_path: Path = DEFAULT_MIXED_PATH,
    thresholds: BatchStressThresholds | None = None,
) -> dict[str, Any]:
    active = thresholds or BatchStressThresholds.from_env()
    large_batch = _run_large_batch(batch_path)
    cli_contract = _run_cli_contract(mixed_path)
    failure_probes = _run_failure_probes()
    errors = _errors(large_batch, cli_contract, failure_probes, active)
    return {
        "ok": not errors,
        "thresholds": active.to_dict(),
        "large_batch": large_batch,
        "cli_contract": cli_contract,
        "failure_probes": failure_probes,
        "errors": errors,
    }


def write_batch_stress_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    large = report["large_batch"]
    cli_contract = report["cli_contract"]
    probes = report["failure_probes"]
    lines = [
        "# Batch Stress Report",
        "",
        f"- ok: `{report['ok']}`",
        f"- tasks: `{large['tasks']}`",
        f"- batch_elapsed_ms: `{large['batch_elapsed_ms']}`",
        f"- tasks_per_second: `{large['tasks_per_second']}`",
        f"- p50_ms: `{large['p50_ms']}`",
        f"- p95_ms: `{large['p95_ms']}`",
        f"- p99_ms: `{large['p99_ms']}`",
        f"- output_contract_pass_rate: `{cli_contract['output_contract_pass_rate']}`",
        f"- controlled_error_rate: `{probes['controlled_error_rate']}`",
        f"- timeout_rate: `{probes['timeout_rate']}`",
        "",
        "## CLI Contract",
        "",
        f"- stdout_clean: `{cli_contract['stdout_clean']}`",
        f"- stderr_has_summary: `{cli_contract['stderr_has_summary']}`",
        f"- output_order_preserved: `{cli_contract['output_order_preserved']}`",
        "",
        "## Failure Probes",
        "",
        f"- local_timeout_controlled: `{probes['local_timeout_controlled']}`",
        f"- intermittent_error_controlled: `{probes['intermittent_error_controlled']}`",
        f"- remote_timeout_controlled: `{probes['remote_timeout_controlled']}`",
        f"- uncontrolled_crashes: `{probes['uncontrolled_crashes']}`",
        "",
        "## Errors",
        "",
    ]
    lines.extend([f"- {error}" for error in report["errors"]] or ["- none"])
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run batch throughput, timeout and partial-failure stress checks.")
    parser.add_argument("--batch", type=Path, default=DEFAULT_BATCH_PATH)
    parser.add_argument("--mixed", type=Path, default=DEFAULT_MIXED_PATH)
    parser.add_argument("--report", type=Path, default=Path("reports/generated/batch-stress.md"))
    parser.add_argument("--check", action="store_true", help="Fail if stress thresholds are not met.")
    args = parser.parse_args()

    report = run_batch_stress(batch_path=args.batch, mixed_path=args.mixed)
    write_batch_stress_report(args.report, report)
    print(json.dumps({"ok": report["ok"], "large_batch": report["large_batch"], "errors": report["errors"]}, sort_keys=True))
    return 0 if report["ok"] or not args.check else 1


def _run_large_batch(path: Path) -> dict[str, Any]:
    tasks = load_jsonl_tasks(path)
    runner = CompetitionRunner(MockCascadeRunner(), dry_run=True)
    results = []
    samples = []
    started = time.perf_counter()
    for task in tasks:
        task_started = time.perf_counter()
        results.append(runner.run(task))
        samples.append((time.perf_counter() - task_started) * 1000)
    elapsed_ms = (time.perf_counter() - started) * 1000
    output_order_preserved = [task.id for task in tasks] == [result.id for result in results]
    return {
        "tasks": len(tasks),
        "batch_elapsed_ms": round(elapsed_ms, 3),
        "tasks_per_second": round((len(tasks) / (elapsed_ms / 1000.0)) if elapsed_ms > 0 else 0.0, 3),
        "p50_ms": round(percentile(samples, 50), 3),
        "p95_ms": round(percentile(samples, 95), 3),
        "p99_ms": round(percentile(samples, 99), 3),
        "output_order_preserved": output_order_preserved,
    }


def _run_cli_contract(path: Path) -> dict[str, Any]:
    tasks = load_jsonl_tasks(path)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        out_path = tmp_root / "mixed-output.jsonl"
        env = os.environ.copy()
        env["ROUTER_MODE"] = "competition"
        env["COMPETITION_DRY_RUN"] = "1"
        env["ROUTER_LOG_PATH"] = str(tmp_root / "run.jsonl")
        completed = subprocess.run(
            [sys.executable, "-m", "router", "run", "--jsonl", str(path), "--out", str(out_path)],
            capture_output=True,
            text=True,
            env=env,
        )
        output_rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()] if out_path.exists() else []
    output_order_preserved = [task.id for task in tasks] == [str(row.get("id")) for row in output_rows]
    stdout_clean = completed.stdout == ""
    stderr_has_summary = '"tasks":' in completed.stderr and str(len(tasks)) in completed.stderr
    output_contracts = [
        isinstance(row.get("answer"), str) and isinstance(row.get("route"), str)
        for row in output_rows
    ]
    return {
        "returncode": completed.returncode,
        "tasks": len(tasks),
        "output_rows": len(output_rows),
        "stdout_clean": stdout_clean,
        "stderr_has_summary": stderr_has_summary,
        "output_order_preserved": output_order_preserved,
        "output_contract_pass_rate": _rate(sum(output_contracts), len(tasks)),
    }


def _run_failure_probes() -> dict[str, Any]:
    local_timeout = _local_timeout_probe()
    intermittent = _intermittent_error_probe()
    remote_timeout = _remote_timeout_probe()
    controlled_errors = (
        local_timeout["controlled_errors"]
        + intermittent["controlled_errors"]
        + remote_timeout["controlled_errors"]
    )
    total_probe_tasks = local_timeout["tasks"] + intermittent["tasks"] + remote_timeout["tasks"]
    timeout_count = local_timeout["timeouts"] + remote_timeout["timeouts"]
    uncontrolled_crashes = (
        local_timeout["uncontrolled_crashes"]
        + intermittent["uncontrolled_crashes"]
        + remote_timeout["uncontrolled_crashes"]
    )
    return {
        "tasks": total_probe_tasks,
        "controlled_errors": controlled_errors,
        "controlled_error_rate": _rate(controlled_errors, total_probe_tasks),
        "timeout_rate": _rate(timeout_count, total_probe_tasks),
        "uncontrolled_crashes": uncontrolled_crashes,
        "local_timeout_controlled": local_timeout["controlled"],
        "intermittent_error_controlled": intermittent["controlled"],
        "remote_timeout_controlled": remote_timeout["controlled"],
        "local_timeout_probe": local_timeout,
        "intermittent_error_probe": intermittent,
        "remote_timeout_probe": remote_timeout,
    }


def _local_timeout_probe() -> dict[str, Any]:
    tasks = [TaskEnvelope(id=f"local-timeout-{index}", input_text="Slow local task") for index in range(3)]
    with FakeOpenAIProvider(config=FakeProviderConfig(response_text="slow", delay_s=0.03)) as provider:
        client = LocalModelClient(base_url=provider.url, model="fake-slow", timeout_s=0.005, max_retries=0)
        runner = LocalM1Runner(client)
        results = [runner.run(task) for task in tasks]
    local_errors = sum(1 for result in results if result.route == "local_error")
    return {
        "tasks": len(tasks),
        "controlled_errors": local_errors,
        "timeouts": local_errors,
        "uncontrolled_crashes": 0,
        "controlled": local_errors == len(tasks),
        "routes": _count_routes(results),
    }


def _intermittent_error_probe() -> dict[str, Any]:
    tasks = [TaskEnvelope(id=f"flaky-{index}", input_text="Flaky local task") for index in range(4)]
    with FakeOpenAIProvider(config=FakeProviderConfig(response_text="ok", statuses=(200, 500, 200, 500))) as provider:
        client = LocalModelClient(base_url=provider.url, model="fake-flaky", timeout_s=1, max_retries=0)
        runner = LocalM1Runner(client)
        results = [runner.run(task) for task in tasks]
    local_errors = sum(1 for result in results if result.route == "local_error")
    return {
        "tasks": len(tasks),
        "controlled_errors": local_errors,
        "timeouts": 0,
        "uncontrolled_crashes": 0,
        "controlled": local_errors == 2,
        "routes": _count_routes(results),
    }


def _remote_timeout_probe() -> dict[str, Any]:
    task = TaskEnvelope(id="remote-timeout-1", input_text="A risky task needs audit.")
    approve_escalate = json.dumps(
        {
            "decision": "escalate",
            "confidence": "low",
            "reason": "force remote timeout probe",
            "failure_modes": ["timeout_probe"],
            "should_generate_alternative": True,
        },
        sort_keys=True,
    )
    with FakeOpenAIProvider(config=FakeProviderConfig(responses=("bad local", approve_escalate, "safe fallback"))) as local:
        with FakeOpenAIProvider(config=FakeProviderConfig(response_text="remote slow", delay_s=0.03)) as remote:
            local_client = LocalModelClient(base_url=local.url, model="fake-local", timeout_s=1, max_retries=0)
            remote_client = FireworksClient(base_url=remote.url, model="fake-fireworks", api_key="fake", timeout_s=0.005, max_retries=0)
            runner = HybridCascadeRunner(local_client, remote_client)
            result = runner.run(task)
    controlled = result.route == "m2b_fireworks_error_approved" and result.metadata.get("fireworks_parse_failed") is False
    return {
        "tasks": 1,
        "controlled_errors": 1 if controlled else 0,
        "timeouts": 1 if controlled else 0,
        "uncontrolled_crashes": 0 if controlled else 1,
        "controlled": controlled,
        "route": result.route,
    }


def _errors(
    large_batch: dict[str, Any],
    cli_contract: dict[str, Any],
    failure_probes: dict[str, Any],
    thresholds: BatchStressThresholds,
) -> list[str]:
    errors = []
    if float(large_batch["batch_elapsed_ms"]) > thresholds.max_batch_elapsed_ms:
        errors.append("large batch elapsed time exceeded threshold")
    if float(large_batch["p95_ms"]) > thresholds.max_p95_ms:
        errors.append("large batch p95 exceeded threshold")
    if float(large_batch["tasks_per_second"]) < thresholds.min_tasks_per_second:
        errors.append("large batch throughput below threshold")
    if not large_batch["output_order_preserved"]:
        errors.append("large batch output order was not preserved")
    if cli_contract["returncode"] != 0:
        errors.append("CLI mixed batch returned non-zero")
    if not cli_contract["stdout_clean"]:
        errors.append("CLI mixed batch polluted stdout")
    if not cli_contract["stderr_has_summary"]:
        errors.append("CLI mixed batch did not emit stderr summary")
    if not cli_contract["output_order_preserved"]:
        errors.append("CLI mixed batch output order was not preserved")
    if float(cli_contract["output_contract_pass_rate"]) < 1.0:
        errors.append("CLI mixed batch output contract failed")
    if int(failure_probes["uncontrolled_crashes"]) > thresholds.max_uncontrolled_crashes:
        errors.append("failure probes had uncontrolled crashes")
    for key in ("local_timeout_controlled", "intermittent_error_controlled", "remote_timeout_controlled"):
        if not failure_probes[key]:
            errors.append(f"{key} is false")
    return errors


def _count_routes(results: list[Any]) -> dict[str, int]:
    routes: dict[str, int] = {}
    for result in results:
        routes[result.route] = routes.get(result.route, 0) + 1
    return routes


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


if __name__ == "__main__":
    raise SystemExit(main())
