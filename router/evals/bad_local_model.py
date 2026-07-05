from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from router.adapters.io import load_jsonl_tasks
from router.core.contracts import AnswerResult, TaskEnvelope
from router.core.local_cascade import LocalCascadeRunner
from router.core.model_client import LocalModelClient
from router.dev.fake_provider import FakeOpenAIProvider, FakeProviderConfig, SCENARIO_RESPONSES
from router.orchestration.competition import CompetitionRunner
from router.orchestration.final_validator import validate_final_answer


DEFAULT_TASKS_PATH = Path("fixtures/chaos/bad-local-model/tasks.jsonl")
REQUIRED_PROFILES = {
    "hallucination_confident",
    "format_drift",
    "empty_or_refusal",
    "verbose_when_strict",
    "wrong_math_plausible",
}


@dataclass(frozen=True)
class BadLocalModelThresholds:
    max_false_approval_rate: float = 0.0
    min_containment_rate: float = 1.0


def run_bad_local_model_drill(
    *,
    tasks_path: Path = DEFAULT_TASKS_PATH,
    thresholds: BadLocalModelThresholds | None = None,
) -> dict[str, Any]:
    active_thresholds = thresholds or BadLocalModelThresholds()
    tasks = load_jsonl_tasks(tasks_path)
    rows = [_run_case(task) for task in tasks]
    metrics = _metrics(rows)
    errors = _errors(rows, metrics, active_thresholds)
    return {
        "ok": not errors,
        "tasks_path": str(tasks_path),
        "thresholds": {
            "max_false_approval_rate": active_thresholds.max_false_approval_rate,
            "min_containment_rate": active_thresholds.min_containment_rate,
        },
        "metrics": metrics,
        "rows": rows,
        "errors": errors,
    }


def write_bad_local_model_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metrics = report["metrics"]
    lines = [
        "# Bad Local Model Chaos Report",
        "",
        f"- ok: `{report['ok']}`",
        f"- tasks: `{metrics['tasks']}`",
        f"- containment_rate: `{metrics['containment_rate']:.3f}`",
        f"- false_approval_rate: `{metrics['false_approval_rate']:.3f}`",
        f"- repair_rate: `{metrics['repair_rate']:.3f}`",
        f"- remote_audit_dry_run_rate: `{metrics['remote_audit_dry_run_rate']:.3f}`",
        f"- strict_format_failure_rate: `{metrics['strict_format_failure_rate']:.3f}`",
        f"- remote_packet_tokens_if_called: `{metrics['remote_packet_tokens_if_called']}`",
        "",
        "## Rows",
        "",
        "| id | profile | protection | action | route | contained | false_approval | answer |",
        "|---|---|---|---|---|---:|---:|---|",
    ]
    for row in report["rows"]:
        lines.append(
            "| "
            f"{row['id']} | "
            f"{row['profile']} | "
            f"{row['expected_protection']} | "
            f"{row['action']} | "
            f"{row['route']} | "
            f"{row['contained']} | "
            f"{row['false_approval']} | "
            f"`{_compact(row['answer'])}` |"
        )
    lines.extend(["", "## Errors", ""])
    lines.extend([f"- {error}" for error in report["errors"]] or ["- none"])
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _run_case(task: TaskEnvelope) -> dict[str, Any]:
    metadata = task.metadata
    profile = _metadata_value(metadata, "chaos_profile")
    responses = _responses_for_case(metadata, profile)
    with FakeOpenAIProvider(
        config=FakeProviderConfig(
            responses=tuple(responses),
            response_text=responses[-1] if responses else "",
            prompt_tokens=12,
            completion_tokens=6,
        )
    ) as provider:
        client = LocalModelClient(base_url=provider.url, model=f"fake-{profile}", max_retries=0, timeout_s=5)
        inner = LocalCascadeRunner(client, policy="balanced")
        runner = CompetitionRunner(inner, dry_run=True)
        result = runner.run(task)
    return _row(task, result, local_calls=len(provider.requests))


def _responses_for_case(metadata: dict[str, Any], profile: str) -> list[str]:
    if profile not in SCENARIO_RESPONSES:
        raise ValueError(f"unknown chaos profile: {profile}")
    m2a_decision = _metadata_value(metadata, "m2a_decision")
    responses = [SCENARIO_RESPONSES[profile], _m2a_response(m2a_decision)]
    if m2a_decision == "escalate":
        responses.append(_metadata_value(metadata, "m2b_response"))
    return responses


def _m2a_response(decision: str) -> str:
    if decision == "approve":
        return json.dumps(
            {
                "decision": "approve",
                "confidence": "high",
                "reason": "chaos verifier overconfidence",
                "failure_modes": [],
                "should_generate_alternative": False,
            },
            sort_keys=True,
        )
    if decision == "escalate":
        return json.dumps(
            {
                "decision": "escalate",
                "confidence": "low",
                "reason": "chaos verifier caught candidate risk",
                "failure_modes": ["bad_local_candidate"],
                "should_generate_alternative": True,
            },
            sort_keys=True,
        )
    raise ValueError(f"unsupported m2a_decision: {decision}")


def _row(task: TaskEnvelope, result: AnswerResult, *, local_calls: int) -> dict[str, Any]:
    decision = result.metadata["competition_trace"]["decision"]
    final_validation = decision["final_validation"]
    expected_protection = _metadata_value(task.metadata, "expected_protection")
    expected_answer = str(task.metadata.get("expected_answer") or "")
    final_check = validate_final_answer(task, result.answer)
    candidate_route = str(result.metadata.get("candidate_route") or "")
    action = str(decision["action"])
    remote_would_call = bool(decision["remote_would_call"])
    final_answer_repaired = bool(decision["final_answer_repaired"])
    local_repaired = candidate_route == "m2b_candidate" and _answer_matches(result.answer, expected_answer)
    validator_repaired = final_answer_repaired and _answer_matches(result.answer, expected_answer)
    contained = _contained(
        expected_protection=expected_protection,
        remote_would_call=remote_would_call,
        local_repaired=local_repaired,
        validator_repaired=validator_repaired,
    )
    false_approval = action == "approve" and not contained
    return {
        "id": task.id,
        "profile": _metadata_value(task.metadata, "chaos_profile"),
        "risk_class": str(task.metadata.get("risk_class") or ""),
        "expected_protection": expected_protection,
        "expected_answer": expected_answer,
        "answer": result.answer,
        "route": result.route,
        "candidate_route": candidate_route,
        "action": action,
        "contained": contained,
        "false_approval": false_approval,
        "local_repaired": local_repaired,
        "validator_repaired": validator_repaired,
        "remote_would_call": remote_would_call,
        "final_answer_repaired": final_answer_repaired,
        "final_validation_reason": final_validation["reason"],
        "strict_format_failure_after_repair": not final_check.valid and final_check.expected_format != "free_text",
        "remote_packet_tokens": int(decision["remote_packet_tokens"]),
        "local_calls": local_calls,
    }


def _contained(
    *,
    expected_protection: str,
    remote_would_call: bool,
    local_repaired: bool,
    validator_repaired: bool,
) -> bool:
    if expected_protection == "remote_audit":
        return remote_would_call
    if expected_protection == "local_repair":
        return local_repaired
    if expected_protection == "final_validator_repair":
        return validator_repaired
    raise ValueError(f"unsupported expected_protection: {expected_protection}")


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tasks = len(rows)
    contained = sum(1 for row in rows if row["contained"])
    false_approvals = sum(1 for row in rows if row["false_approval"])
    repairs = sum(1 for row in rows if row["local_repaired"] or row["validator_repaired"])
    remote_dry_runs = sum(1 for row in rows if row["remote_would_call"])
    strict_failures = sum(1 for row in rows if row["strict_format_failure_after_repair"])
    profiles = sorted({str(row["profile"]) for row in rows})
    return {
        "tasks": tasks,
        "profiles": profiles,
        "required_profiles_present": sorted(REQUIRED_PROFILES.intersection(profiles)),
        "containment_rate": _rate(contained, tasks),
        "contained": contained,
        "uncontained": tasks - contained,
        "false_approvals": false_approvals,
        "false_approval_rate": _rate(false_approvals, tasks),
        "repair_rate": _rate(repairs, tasks),
        "local_repair_rate": _rate(sum(1 for row in rows if row["local_repaired"]), tasks),
        "final_validator_repair_rate": _rate(sum(1 for row in rows if row["validator_repaired"]), tasks),
        "remote_audit_dry_run_rate": _rate(remote_dry_runs, tasks),
        "strict_format_failure_rate": _rate(strict_failures, tasks),
        "remote_packet_tokens_if_called": sum(row["remote_packet_tokens"] for row in rows if row["remote_would_call"]),
        "local_calls": sum(row["local_calls"] for row in rows),
    }


def _errors(
    rows: list[dict[str, Any]],
    metrics: dict[str, Any],
    thresholds: BadLocalModelThresholds,
) -> list[str]:
    errors: list[str] = []
    missing_profiles = sorted(REQUIRED_PROFILES - set(metrics["profiles"]))
    if missing_profiles:
        errors.append(f"missing chaos profiles: {', '.join(missing_profiles)}")
    if float(metrics["false_approval_rate"]) > thresholds.max_false_approval_rate:
        errors.append(
            "false approval rate "
            f"{metrics['false_approval_rate']:.3f} exceeds {thresholds.max_false_approval_rate:.3f}"
        )
    if float(metrics["containment_rate"]) < thresholds.min_containment_rate:
        errors.append(
            "containment rate "
            f"{metrics['containment_rate']:.3f} below {thresholds.min_containment_rate:.3f}"
        )
    for row in rows:
        if not row["contained"]:
            errors.append(f"{row['id']}: bad local candidate was not contained")
        if row["strict_format_failure_after_repair"]:
            errors.append(f"{row['id']}: strict format still invalid after repair")
    return errors


def _metadata_value(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    if value is None or str(value) == "":
        raise ValueError(f"missing metadata.{key}")
    return str(value)


def _answer_matches(answer: str, expected: str) -> bool:
    return not expected or answer.strip() == expected.strip()


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _compact(value: str, max_chars: int = 96) -> str:
    compacted = " ".join(value.split())
    if len(compacted) <= max_chars:
        return compacted
    return compacted[: max_chars - 3].rstrip() + "..."
