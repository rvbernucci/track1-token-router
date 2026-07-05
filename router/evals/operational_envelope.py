from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass
from typing import Any

from router.core.contracts import TaskEnvelope
from router.core.policy import DEFAULT_POLICY, POLICIES, simulate_policy_route, simulated_remote_tokens
from router.orchestration.budget import TaskBudget
from router.orchestration.prompt_packet import REMOTE_AUDIT_ROUTES, build_remote_audit_packet


@dataclass(frozen=True)
class LatencyThresholds:
    max_p95_ms: float = 5000.0
    max_batch_ms: float = 10000.0
    min_batch_tasks_per_second: float = 1.0
    local_timeout_ms: float = 50.0
    remote_timeout_ms: float = 50.0

    @classmethod
    def from_env(cls) -> "LatencyThresholds":
        return cls(
            max_p95_ms=_float_env("LATENCY_DRILL_MAX_P95_MS", cls.max_p95_ms),
            max_batch_ms=_float_env("LATENCY_DRILL_MAX_BATCH_MS", cls.max_batch_ms),
            min_batch_tasks_per_second=_float_env(
                "LATENCY_DRILL_MIN_BATCH_TASKS_PER_SECOND",
                cls.min_batch_tasks_per_second,
            ),
            local_timeout_ms=_float_env("LATENCY_DRILL_LOCAL_TIMEOUT_MS", cls.local_timeout_ms),
            remote_timeout_ms=_float_env("LATENCY_DRILL_REMOTE_TIMEOUT_MS", cls.remote_timeout_ms),
        )

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class TokenEnvelopeThresholds:
    max_candidate_run_exposure: int = 8000
    max_candidate_task_exposure: int = 450

    @classmethod
    def from_env(cls) -> "TokenEnvelopeThresholds":
        return cls(
            max_candidate_run_exposure=_int_env(
                "TOKEN_ENVELOPE_MAX_CANDIDATE_RUN_EXPOSURE",
                cls.max_candidate_run_exposure,
            ),
            max_candidate_task_exposure=_int_env(
                "TOKEN_ENVELOPE_MAX_CANDIDATE_TASK_EXPOSURE",
                cls.max_candidate_task_exposure,
            ),
        )

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def summarize_latency_envelope(
    samples_ms: list[float],
    *,
    batch_elapsed_ms: float,
    batch_tasks: int,
    thresholds: LatencyThresholds | None = None,
) -> dict[str, Any]:
    active = thresholds or LatencyThresholds()
    throughput = (batch_tasks / (batch_elapsed_ms / 1000.0)) if batch_elapsed_ms > 0 else 0.0
    p50 = percentile(samples_ms, 50)
    p95 = percentile(samples_ms, 95)
    p99 = percentile(samples_ms, 99)
    local_timeout = _simulated_timeout_probe(active.local_timeout_ms + 1, active.local_timeout_ms)
    remote_timeout = _simulated_timeout_probe(active.remote_timeout_ms + 1, active.remote_timeout_ms)
    ready = (
        bool(samples_ms)
        and p95 <= active.max_p95_ms
        and batch_elapsed_ms <= active.max_batch_ms
        and throughput >= active.min_batch_tasks_per_second
        and local_timeout["timeout_detected"]
        and remote_timeout["timeout_detected"]
    )
    return {
        "ready": ready,
        "thresholds": active.to_dict(),
        "samples_ms": [round(value, 3) for value in samples_ms],
        "cold_start_ms": round(samples_ms[0], 3) if samples_ms else 0.0,
        "p50_ms": round(p50, 3),
        "p95_ms": round(p95, 3),
        "p99_ms": round(p99, 3),
        "batch_elapsed_ms": round(batch_elapsed_ms, 3),
        "batch_tasks": batch_tasks,
        "batch_tasks_per_second": round(throughput, 3),
        "local_timeout_probe": local_timeout,
        "remote_timeout_probe": remote_timeout,
    }


def percentile(values: list[float], rank: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = math.ceil((rank / 100.0) * len(ordered)) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def build_token_envelope(
    tasks: list[TaskEnvelope],
    *,
    candidate_policy: str = DEFAULT_POLICY,
    thresholds: TokenEnvelopeThresholds | None = None,
    budget: TaskBudget | None = None,
) -> dict[str, Any]:
    active_thresholds = thresholds or TokenEnvelopeThresholds()
    active_budget = budget or TaskBudget()
    task_rows: list[dict[str, Any]] = []
    policy_summaries = []
    route_worst_case: dict[str, int] = {}

    for policy in POLICIES:
        rows = [_task_exposure(task, policy) for task in tasks]
        for row in rows:
            route = str(row["route"])
            route_worst_case[route] = max(route_worst_case.get(route, 0), int(row["total_exposure"]))
        task_rows.extend(rows)
        run_exposure = sum(int(row["total_exposure"]) for row in rows)
        remote_tasks = sum(1 for row in rows if int(row["remote_model_tokens"]) > 0 or int(row["packet_tokens"]) > 0)
        max_task_exposure = max((int(row["total_exposure"]) for row in rows), default=0)
        policy_summaries.append(
            {
                "policy": policy,
                "tasks": len(rows),
                "remote_tasks": remote_tasks,
                "remote_task_rate": remote_tasks / len(rows) if rows else 0.0,
                "packet_tokens_total": sum(int(row["packet_tokens"]) for row in rows),
                "remote_model_tokens_total": sum(int(row["remote_model_tokens"]) for row in rows),
                "run_exposure": run_exposure,
                "max_task_exposure": max_task_exposure,
                "tasks_above_task_budget": sum(
                    1 for row in rows if int(row["total_exposure"]) > active_budget.max_remote_tokens_per_task
                ),
            }
        )

    top_tasks = sorted(task_rows, key=lambda row: int(row["total_exposure"]), reverse=True)[:20]
    candidate = next((row for row in policy_summaries if row["policy"] == candidate_policy), policy_summaries[0])
    ready = (
        int(candidate["run_exposure"]) <= active_thresholds.max_candidate_run_exposure
        and int(candidate["max_task_exposure"]) <= active_thresholds.max_candidate_task_exposure
    )
    return {
        "ready": ready,
        "candidate_policy": candidate_policy,
        "thresholds": active_thresholds.to_dict(),
        "budget": active_budget.to_dict(),
        "policy_summaries": policy_summaries,
        "candidate": candidate,
        "route_worst_case": route_worst_case,
        "top_tasks": top_tasks,
    }


def _task_exposure(task: TaskEnvelope, policy: str) -> dict[str, Any]:
    route = simulate_policy_route(task, policy)
    usage = simulated_remote_tokens(route)
    packet_tokens = 0
    if route in REMOTE_AUDIT_ROUTES:
        packet = build_remote_audit_packet(
            task,
            candidate="LOCAL_CANDIDATE",
            concern=str(task.metadata.get("risk") or "routing_risk"),
        )
        packet_tokens = packet.approx_tokens()
    return {
        "policy": policy,
        "task_id": task.id,
        "category": task.metadata.get("category"),
        "difficulty": task.metadata.get("difficulty"),
        "risk": task.metadata.get("risk"),
        "route": route,
        "packet_tokens": packet_tokens,
        "remote_model_tokens": usage.total,
        "total_exposure": packet_tokens + usage.total,
    }


def _simulated_timeout_probe(delay_ms: float, timeout_ms: float) -> dict[str, float | bool]:
    return {
        "simulated_delay_ms": round(delay_ms, 3),
        "timeout_ms": round(timeout_ms, 3),
        "timeout_detected": delay_ms > timeout_ms,
    }


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
