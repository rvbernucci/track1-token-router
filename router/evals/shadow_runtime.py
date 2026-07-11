from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from router.core.contracts import TaskAssessment, TaskEnvelope
from router.orchestration.assessment import build_feature_vector, compute_structural_features
from router.orchestration.final_validator import apply_answer_contract
from router.orchestration.local_adjudication import (
    LocalAdjudicationPolicy,
    build_local_adjudication_evidence,
)
from router.orchestration.solvers import solve_deterministic


class ShadowVariant(str, Enum):
    FIREWORKS_ONLY = "fireworks_only"
    DETERMINISTIC_FIREWORKS = "deterministic_fireworks"
    E2B_REGRESSION = "e2b_regression_without_proofs"
    PROOF_E2B = "proof_plus_e2b_cross_validation"
    FULL_BINARY = "full_cohort_binary_adjudication"


@dataclass(frozen=True)
class ShadowResult:
    task_id: str
    answer: str
    route: str
    remote_prompt_tokens: int
    remote_completion_tokens: int
    simulated_latency_ms: float
    simulated_peak_memory_mb: float
    local_release: bool
    proof: Mapping[str, Any] | None = None
    error: str = ""

    @property
    def remote_tokens(self) -> int:
        return self.remote_prompt_tokens + self.remote_completion_tokens

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["proof"] = dict(self.proof) if self.proof else None
        payload["remote_tokens"] = self.remote_tokens
        return payload


class FrozenFireworksAdapter:
    def __init__(self, *, base_url: str, allowed_models: Sequence[str]) -> None:
        self.base_url = base_url.strip()
        self.allowed_models = tuple(model.strip() for model in allowed_models if model.strip())
        if not self.base_url:
            raise ValueError("FIREWORKS_BASE_URL is required for frozen remote replay.")
        if not self.allowed_models:
            raise ValueError("ALLOWED_MODELS is required for frozen remote replay.")

    def complete(self, row: Mapping[str, Any]) -> ShadowResult:
        task_id = _required_string(row, "task_id")
        frozen = row.get("frozen_fireworks")
        if not isinstance(frozen, Mapping):
            raise ValueError("Frozen Fireworks artifact is missing.")
        model = _required_string(frozen, "model")
        LocalAdjudicationPolicy.authorize_remote_model(model, self.allowed_models)
        answer = frozen.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Frozen Fireworks answer is malformed.")
        prompt_tokens = _non_negative_int(frozen.get("prompt_tokens"), "prompt_tokens")
        completion_tokens = _non_negative_int(frozen.get("completion_tokens"), "completion_tokens")
        latency = _non_negative_float(frozen.get("latency_ms"), "latency_ms")
        return ShadowResult(
            task_id=task_id,
            answer=answer.strip(),
            route="fireworks_replay",
            remote_prompt_tokens=prompt_tokens,
            remote_completion_tokens=completion_tokens,
            simulated_latency_ms=latency,
            simulated_peak_memory_mb=96.0,
            local_release=False,
        )


class FrozenE2BAdapter:
    def candidate(self, row: Mapping[str, Any]) -> tuple[str, float, float]:
        frozen = row.get("frozen_e2b")
        if not isinstance(frozen, Mapping):
            raise ValueError("Frozen E2B artifact is missing.")
        answer = frozen.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Frozen E2B candidate is malformed.")
        return (
            answer,
            _non_negative_float(frozen.get("latency_ms"), "e2b.latency_ms"),
            _non_negative_float(frozen.get("peak_memory_mb"), "e2b.peak_memory_mb"),
        )


class ShadowRuntime:
    def __init__(
        self,
        *,
        variant: ShadowVariant,
        local_policy: LocalAdjudicationPolicy,
        fireworks: FrozenFireworksAdapter,
        deadline_ms: float = 570_000.0,
        reserve_ms: float = 5_000.0,
    ) -> None:
        if deadline_ms <= 0 or reserve_ms < 0 or reserve_ms >= deadline_ms:
            raise ValueError("Shadow deadline and reserve are invalid.")
        self.variant = variant
        self.local_policy = local_policy
        self.fireworks = fireworks
        self.e2b = FrozenE2BAdapter()
        self.deadline_ms = deadline_ms
        self.reserve_ms = reserve_ms

    def run(self, rows: Sequence[Mapping[str, Any]]) -> list[ShadowResult]:
        task_ids = [_required_string(row, "task_id") for row in rows]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Shadow input contains duplicate task IDs.")
        results: list[ShadowResult] = []
        elapsed_ms = 0.0
        for row in rows:
            if elapsed_ms >= self.deadline_ms - self.reserve_ms:
                result = _timeout_result(_required_string(row, "task_id"))
            else:
                result = self._run_one(row, remaining_ms=self.deadline_ms - self.reserve_ms - elapsed_ms)
            results.append(result)
            elapsed_ms += result.simulated_latency_ms
        if [result.task_id for result in results] != task_ids:
            raise ValueError("Shadow output order differs from input order.")
        return results

    def _run_one(self, row: Mapping[str, Any], *, remaining_ms: float) -> ShadowResult:
        task = TaskEnvelope(id=_required_string(row, "task_id"), input_text=_required_string(row, "prompt"))
        try:
            if self.variant is ShadowVariant.FIREWORKS_ONLY:
                return self.fireworks.complete(row)
            if self.variant is ShadowVariant.DETERMINISTIC_FIREWORKS:
                solved = solve_deterministic(task)
                if solved:
                    evidence = build_local_adjudication_evidence(task, solved.answer)
                    if evidence.hard_gate_passed:
                        return _evidence_result(
                            task,
                            evidence,
                            route="verified_deterministic",
                            latency=2.0,
                            memory=48.0,
                        )
                return self.fireworks.complete(row)
            if self.variant is ShadowVariant.E2B_REGRESSION:
                return self._e2b_regression(task, row)
            if self.variant is ShadowVariant.PROOF_E2B:
                return self._proof_e2b(task, row)
            return self._full_binary(task, row, remaining_ms=remaining_ms)
        except Exception as exc:
            return ShadowResult(
                task_id=task.id or "unknown",
                answer="Unable to produce a valid answer.",
                route="shadow_failure_fallback",
                remote_prompt_tokens=0,
                remote_completion_tokens=0,
                simulated_latency_ms=1.0,
                simulated_peak_memory_mb=32.0,
                local_release=False,
                error=type(exc).__name__,
            )

    def _e2b_regression(self, task: TaskEnvelope, row: Mapping[str, Any]) -> ShadowResult:
        assessment = _assessment(row)
        candidate, latency, memory = self.e2b.candidate(row)
        validation = apply_answer_contract(task, candidate)
        scores = assessment.scores
        if validation.valid and scores.deterministic_fit >= 6 and scores.knowledge_uncertainty <= 2:
            return ShadowResult(
                task_id=task.id or "unknown",
                answer=validation.answer,
                route="e2b_regression_local",
                remote_prompt_tokens=0,
                remote_completion_tokens=0,
                simulated_latency_ms=latency,
                simulated_peak_memory_mb=memory,
                local_release=True,
            )
        remote = self.fireworks.complete(row)
        return _add_probe_cost(remote, latency, memory)

    def _proof_e2b(self, task: TaskEnvelope, row: Mapping[str, Any]) -> ShadowResult:
        solved = solve_deterministic(task)
        if solved:
            evidence = build_local_adjudication_evidence(task, solved.answer)
            if evidence.hard_gate_passed:
                return _evidence_result(task, evidence, route="verified_deterministic", latency=2.0, memory=48.0)
        candidate, latency, memory = self.e2b.candidate(row)
        evidence = build_local_adjudication_evidence(task, candidate)
        if evidence.hard_gate_passed:
            return _evidence_result(task, evidence, route="verified_e2b", latency=latency, memory=memory)
        return _add_probe_cost(self.fireworks.complete(row), latency, memory)

    def _full_binary(self, task: TaskEnvelope, row: Mapping[str, Any], *, remaining_ms: float) -> ShadowResult:
        solved = solve_deterministic(task)
        if solved:
            evidence = build_local_adjudication_evidence(task, solved.answer)
            if evidence.hard_gate_passed:
                return _evidence_result(task, evidence, route="verified_deterministic", latency=2.0, memory=48.0)
        assessment = _assessment(row)
        features = build_feature_vector(
            assessment,
            compute_structural_features(task, deadline_remaining_ms=max(0, int(remaining_ms))),
        )
        probe = self.local_policy.should_probe(features, deadline_remaining_ms=max(0, int(remaining_ms)))
        if probe.probe:
            candidate, latency, memory = self.e2b.candidate(row)
            decision = self.local_policy.adjudicate(
                task,
                candidate,
                features,
                deadline_remaining_ms=max(0, int(remaining_ms - latency)),
            )
            if decision.accepted and decision.evidence:
                return _evidence_result(task, decision.evidence, route="binary_verified_e2b", latency=latency, memory=memory)
            return _add_probe_cost(self.fireworks.complete(row), latency, memory)
        return self.fireworks.complete(row)


def _assessment(row: Mapping[str, Any]) -> TaskAssessment:
    payload = row.get("assessment")
    if not isinstance(payload, Mapping):
        raise ValueError("Frozen FunctionGemma assessment is missing.")
    return TaskAssessment.from_mapping(payload)


def _evidence_result(task: TaskEnvelope, evidence: Any, *, route: str, latency: float, memory: float) -> ShadowResult:
    return ShadowResult(
        task_id=task.id or "unknown",
        answer=evidence.normalized_answer,
        route=route,
        remote_prompt_tokens=0,
        remote_completion_tokens=0,
        simulated_latency_ms=latency,
        simulated_peak_memory_mb=memory,
        local_release=True,
        proof=evidence.to_dict(),
    )


def _add_probe_cost(remote: ShadowResult, latency: float, memory: float) -> ShadowResult:
    return ShadowResult(
        task_id=remote.task_id,
        answer=remote.answer,
        route=remote.route,
        remote_prompt_tokens=remote.remote_prompt_tokens,
        remote_completion_tokens=remote.remote_completion_tokens,
        simulated_latency_ms=remote.simulated_latency_ms + latency,
        simulated_peak_memory_mb=max(remote.simulated_peak_memory_mb, memory),
        local_release=False,
        proof=remote.proof,
        error=remote.error,
    )


def _timeout_result(task_id: str) -> ShadowResult:
    return ShadowResult(
        task_id=task_id,
        answer="Unable to complete the task within the available time budget.",
        route="shadow_deadline_exhausted",
        remote_prompt_tokens=0,
        remote_completion_tokens=0,
        simulated_latency_ms=0.0,
        simulated_peak_memory_mb=32.0,
        local_release=False,
    )


def _required_string(payload: Mapping[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value.strip()


def _non_negative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return value


def _non_negative_float(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math_is_finite(float(value)) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return float(value)


def math_is_finite(value: float) -> bool:
    return value == value and value not in {float("inf"), float("-inf")}
