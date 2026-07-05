from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from router.core.contracts import AnswerResult, TaskEnvelope
from router.core.guardrails import evaluate_guardrail
from router.core.logging import JsonlRunLogger
from router.core.runner import TaskRunner
from router.orchestration.final_validator import validate_final_answer


ORCHESTRATION_STATES = (
    "received",
    "guardrail",
    "deterministic_solver",
    "m1_candidate",
    "local_verify",
    "local_repair",
    "remote_audit",
    "final",
    "failed",
)

ORCHESTRATION_EVENTS = (
    "start",
    "skip",
    "approve",
    "escalate",
    "replace",
    "fallback",
    "error",
)

FALLBACK_MAP = {
    "local_error": "return_controlled_local_error",
    "m2b_error_return_m1": "return_m1_candidate_after_repair_error",
    "m2b_fireworks_error_approved": "return_m2b_after_remote_error",
    "fireworks_parse_failed": "replace_with_remote_raw_text",
}


@dataclass(frozen=True)
class OrchestrationStep:
    state: str
    event: str
    reason: str = ""
    route: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "event": self.event,
            "reason": self.reason,
            "route": self.route,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class OrchestrationTrace:
    task_id: str | None
    final_route: str
    steps: list[OrchestrationStep]
    fallback: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "final_route": self.final_route,
            "fallback": self.fallback,
            "steps": [step.to_dict() for step in self.steps],
        }


class OrchestratedRunner:
    """Adds an explicit state-machine trace around an existing runner."""

    def __init__(
        self,
        inner: TaskRunner,
        *,
        logger: JsonlRunLogger | None = None,
        enable_guardrails: bool = False,
    ) -> None:
        self.inner = inner
        self.logger = logger
        self.enable_guardrails = enable_guardrails

    def run(self, task: TaskEnvelope) -> AnswerResult:
        if self.enable_guardrails:
            guardrail = evaluate_guardrail(task)
            if guardrail is not None:
                result = AnswerResult(
                    id=task.id,
                    answer=guardrail.answer,
                    route=guardrail.route,
                    metadata={
                        "runner": "orchestrated_guardrail",
                        "reason": guardrail.reason,
                    },
                )
                trace = build_orchestration_trace(task, result, guardrail_reason=guardrail.reason)
                result = _with_trace_and_validation(task, result, trace)
                if self.logger:
                    self.logger.log_result(
                        task,
                        result,
                        extra={
                            "stage": "orchestration_state_machine",
                            "orchestration_trace": trace.to_dict(),
                        },
                    )
                return result

        result = self.inner.run(task)
        trace = build_orchestration_trace(task, result)
        return _with_trace_and_validation(task, result, trace)


def build_orchestration_trace(
    task: TaskEnvelope,
    result: AnswerResult,
    *,
    guardrail_reason: str = "",
) -> OrchestrationTrace:
    steps = [
        OrchestrationStep(
            state="received",
            event="start",
            reason="task_received",
            route=result.route,
        )
    ]
    fallback = ""

    if result.route.startswith("guardrail_"):
        steps.append(
            OrchestrationStep(
                state="guardrail",
                event="approve",
                reason=guardrail_reason or result.metadata.get("reason", "deterministic_guardrail"),
                route=result.route,
            )
        )
        steps.append(OrchestrationStep(state="final", event="approve", reason="guardrail_final", route=result.route))
        return OrchestrationTrace(task_id=task.id, final_route=result.route, steps=steps)

    steps.append(OrchestrationStep(state="guardrail", event="skip", reason="no_guardrail_match", route=result.route))

    if result.route.startswith("solver_"):
        steps.append(
            OrchestrationStep(
                state="deterministic_solver",
                event="approve",
                reason=result.metadata.get("reason", "deterministic_solver_high_confidence"),
                route=result.route,
            )
        )
        steps.append(OrchestrationStep(state="final", event="approve", reason="solver_final", route=result.route))
        return OrchestrationTrace(task_id=task.id, final_route=result.route, steps=steps)

    if result.route == "local_error":
        fallback = FALLBACK_MAP["local_error"]
        steps.extend(
            [
                OrchestrationStep(state="m1_candidate", event="error", reason="local_model_error", route=result.route),
                OrchestrationStep(state="failed", event="fallback", reason=fallback, route=result.route),
                OrchestrationStep(state="final", event="fallback", reason=fallback, route=result.route),
            ]
        )
        return OrchestrationTrace(task_id=task.id, final_route=result.route, steps=steps, fallback=fallback)

    steps.append(OrchestrationStep(state="m1_candidate", event="approve", reason="candidate_generated", route=result.route))

    if result.route == "m1_approved":
        steps.extend(
            [
                OrchestrationStep(state="local_verify", event="approve", reason="local_verifier_approved", route=result.route),
                OrchestrationStep(state="final", event="approve", reason="return_m1_candidate", route=result.route),
            ]
        )
        return OrchestrationTrace(task_id=task.id, final_route=result.route, steps=steps)

    if result.route == "m2b_error_return_m1":
        fallback = FALLBACK_MAP["m2b_error_return_m1"]
        steps.extend(
            [
                OrchestrationStep(state="local_verify", event="escalate", reason="local_verifier_escalated", route=result.route),
                OrchestrationStep(state="local_repair", event="error", reason="repair_generation_failed", route=result.route),
                OrchestrationStep(state="failed", event="fallback", reason=fallback, route=result.route),
                OrchestrationStep(state="final", event="fallback", reason=fallback, route=result.route),
            ]
        )
        return OrchestrationTrace(task_id=task.id, final_route=result.route, steps=steps, fallback=fallback)

    if result.route == "m2b_candidate":
        steps.extend(
            [
                OrchestrationStep(state="local_verify", event="escalate", reason="local_verifier_escalated", route=result.route),
                OrchestrationStep(state="local_repair", event="approve", reason="local_repair_candidate", route=result.route),
                OrchestrationStep(state="final", event="approve", reason="return_m2b_candidate", route=result.route),
            ]
        )
        return OrchestrationTrace(task_id=task.id, final_route=result.route, steps=steps)

    if result.route == "m2b_fireworks_approved":
        steps.extend(_remote_steps(result.route, "approve", "remote_auditor_approved"))
        return OrchestrationTrace(task_id=task.id, final_route=result.route, steps=steps)

    if result.route == "m2b_fireworks_error_approved":
        fallback = FALLBACK_MAP["m2b_fireworks_error_approved"]
        steps.extend(_remote_steps(result.route, "fallback", fallback))
        return OrchestrationTrace(task_id=task.id, final_route=result.route, steps=steps, fallback=fallback)

    if result.route == "fireworks_replaced":
        parse_failed = bool(result.metadata.get("fireworks_parse_failed"))
        event = "fallback" if parse_failed else "replace"
        reason = FALLBACK_MAP["fireworks_parse_failed"] if parse_failed else "remote_auditor_replaced"
        fallback = reason if parse_failed else ""
        steps.extend(_remote_steps(result.route, event, reason))
        return OrchestrationTrace(task_id=task.id, final_route=result.route, steps=steps, fallback=fallback)

    steps.append(OrchestrationStep(state="final", event="fallback", reason="unknown_route_returned", route=result.route))
    return OrchestrationTrace(task_id=task.id, final_route=result.route, steps=steps, fallback="unknown_route_returned")


def write_state_machine_json(path: Path, traces: list[OrchestrationTrace]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([trace.to_dict() for trace in traces], ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_state_machine_report(path: Path, traces: list[OrchestrationTrace]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state_counts: dict[str, int] = {}
    route_counts: dict[str, int] = {}
    for trace in traces:
        route_counts[trace.final_route] = route_counts.get(trace.final_route, 0) + 1
        for step in trace.steps:
            state_counts[step.state] = state_counts.get(step.state, 0) + 1

    lines = [
        "# State Machine Report",
        "",
        f"- traces: {len(traces)}",
        "",
        "## Routes",
        "",
        "| route | count |",
        "|---|---:|",
    ]
    for route, count in sorted(route_counts.items()):
        lines.append(f"| {route} | {count} |")
    lines.extend(["", "## States", "", "| state | count |", "|---|---:|"])
    for state, count in sorted(state_counts.items()):
        lines.append(f"| {state} | {count} |")
    lines.extend(
        [
            "",
            "## Canonical Flow",
            "",
            "```text",
            "received -> guardrail -> m1_candidate -> local_verify -> local_repair -> remote_audit -> final",
            "                 \\-> deterministic_solver -> final",
            "                                      \\-> failed -> final",
            "```",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _remote_steps(route: str, remote_event: str, remote_reason: str) -> list[OrchestrationStep]:
    return [
        OrchestrationStep(state="local_verify", event="escalate", reason="local_verifier_escalated", route=route),
        OrchestrationStep(state="local_repair", event="approve", reason="local_repair_candidate", route=route),
        OrchestrationStep(state="remote_audit", event=remote_event, reason=remote_reason, route=route),
        OrchestrationStep(state="final", event=remote_event, reason=remote_reason, route=route),
    ]


def _with_trace(result: AnswerResult, trace: OrchestrationTrace) -> AnswerResult:
    metadata = dict(result.metadata)
    metadata["orchestration_trace"] = trace.to_dict()
    return AnswerResult(
        id=result.id,
        answer=result.answer,
        route=result.route,
        remote_tokens=result.remote_tokens,
        metadata=metadata,
    )


def _with_trace_and_validation(task: TaskEnvelope, result: AnswerResult, trace: OrchestrationTrace) -> AnswerResult:
    with_trace = _with_trace(result, trace)
    metadata = dict(with_trace.metadata)
    validation = validate_final_answer(task, result.answer)
    metadata["final_validation"] = validation.to_dict()
    final_answer = with_trace.answer
    if not validation.valid and validation.repaired_answer:
        final_answer = validation.repaired_answer
        metadata["final_answer_repaired"] = True
    return AnswerResult(
        id=with_trace.id,
        answer=final_answer,
        route=with_trace.route,
        remote_tokens=with_trace.remote_tokens,
        metadata=metadata,
    )
