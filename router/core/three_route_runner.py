from __future__ import annotations

from dataclasses import replace
from time import monotonic
from router.core.contracts import AnswerResult, Engine, EngineDecision, EnginePrediction, RoutingTrace, TaskEnvelope, TokenUsage
from router.core.logging import JsonlRunLogger
from router.core.runner import TaskRunner
from router.functiongemma.provider import FunctionGemmaAssessmentProvider, FunctionGemmaProviderError
from router.functiongemma.tool_planner_provider import FunctionGemmaToolPlannerError, FunctionGemmaToolPlannerProvider
from router.core.tool_augmented_runner import is_tool_planner_candidate
from router.orchestration.assessment import build_feature_vector, compute_structural_features
from router.orchestration.final_validator import validate_or_safely_repair_final_answer
from router.orchestration.e2b_selective_gate import E2BSelectivePolicy
from router.orchestration.e2b_extra_trees_gate import E2BExtraTreesGate
from router.orchestration.e2b_matrix_gate import E2BMatrixGate
from router.orchestration.game_theory_selector import MinimaxRegretSelector, deterministic_solver_prediction
from router.orchestration.outcome_models import OutcomeModelPredictor
from router.orchestration.risk_ladder import RiskLadderPolicy
from router.orchestration.solvers import SolverResult, solve_deterministic
from router.orchestration.tool_executor import run_validated_tool_plan


class ThreeRouteRunner:
    def __init__(
        self,
        *,
        assessment_provider: FunctionGemmaAssessmentProvider,
        predictor: OutcomeModelPredictor,
        selector: MinimaxRegretSelector,
        e2b_runner: TaskRunner,
        fireworks_runner: TaskRunner,
        selective_policy: E2BSelectivePolicy | None = None,
        matrix_gate: E2BMatrixGate | None = None,
        extra_trees_gate: E2BExtraTreesGate | None = None,
        risk_ladder: RiskLadderPolicy | None = None,
        tool_planner_provider: FunctionGemmaToolPlannerProvider | None = None,
        logger: JsonlRunLogger | None = None,
        task_deadline_ms: int = 10 * 60 * 1000,
        e2b_min_remaining_ms: int = 30_000,
        e2b_retry_latest_start_ms: int = 3_000,
    ) -> None:
        self.assessment_provider = assessment_provider
        self.predictor = predictor
        self.selector = selector
        self.e2b_runner = e2b_runner
        self.fireworks_runner = fireworks_runner
        self.selective_policy = selective_policy
        self.matrix_gate = matrix_gate
        self.extra_trees_gate = extra_trees_gate
        self.risk_ladder = risk_ladder
        self.tool_planner_provider = tool_planner_provider
        self.logger = logger
        self.task_deadline_ms = task_deadline_ms
        self.e2b_min_remaining_ms = e2b_min_remaining_ms
        self.e2b_retry_latest_start_ms = e2b_retry_latest_start_ms
        self.run_deadline: float | None = None

    def set_run_deadline(self, deadline_monotonic: float) -> None:
        if deadline_monotonic <= 0:
            raise ValueError("Run deadline must be a positive monotonic timestamp.")
        self.run_deadline = deadline_monotonic

    def run(self, task: TaskEnvelope) -> AnswerResult:
        started = monotonic()
        solver = solve_deterministic(task)
        if solver is not None:
            decision = EngineDecision(
                engine=Engine.DETERMINISTIC,
                reason="proof_carrying_solver_precedes_model_assessment",
                feasible_engines=(Engine.DETERMINISTIC, Engine.FIREWORKS),
                probability_correct=1.0,
            )
            trace = RoutingTrace(
                task_id=task.id,
                assessment=None,
                features=None,
                predictions=(deterministic_solver_prediction(accepted=True),),
                decision=decision,
            )
            candidate = _solver_result(task, solver)
            result = AnswerResult(
                id=candidate.id,
                answer=candidate.answer,
                route=candidate.route,
                remote_tokens=candidate.remote_tokens,
                metadata={**candidate.metadata, "routing_trace": trace.to_dict()},
            )
            self._log(task, result, trace)
            return result
        try:
            invocation = self.assessment_provider.assess_with_trace(task)
            task_remaining = self.task_deadline_ms - round((monotonic() - started) * 1000)
            run_remaining = (
                round((self.run_deadline - monotonic()) * 1000)
                if self.run_deadline is not None
                else self.task_deadline_ms
            )
            remaining = max(0, min(task_remaining, run_remaining))
            features = build_feature_vector(
                invocation.assessment,
                compute_structural_features(task, deadline_remaining_ms=remaining),
            )
            predictions = self._predictions(task, features, solver)
            uncertainty = {
                engine: 0.0 if engine is Engine.DETERMINISTIC else self.predictor.uncertainty(prediction)
                for engine, prediction in predictions.items()
            }
            selection = self.selector.select_with_trace(
                features,
                predictions,
                probability_uncertainty=uncertainty,
            )
            # The matrix was fitted on raw FunctionGemma outputs; calibrated scores belong
            # to the legacy outcome selector and would shift the learned decision boundary.
            matrix_decision = (
                self.matrix_gate.decide(invocation.raw_assessment, task.input_text)
                if self.matrix_gate else None
            )
            risk_decision = (
                self.risk_ladder.decide(
                    intent=invocation.raw_assessment.intent.value,
                    probability=matrix_decision.probability,
                    remaining_ms=remaining,
                )
                if self.risk_ladder is not None and matrix_decision is not None else None
            )
            if matrix_decision is not None and matrix_decision.probe and risk_decision is not None and risk_decision.action != "e2b":
                matrix_decision = replace(
                    matrix_decision, probe=False,
                    reason=f"risk_ladder_{risk_decision.action}",
                )
            if matrix_decision is not None and matrix_decision.probe and remaining < self.e2b_min_remaining_ms:
                matrix_decision = replace(matrix_decision, probe=False, reason="matrix_deadline_guard")
        except (FunctionGemmaProviderError, OSError, TimeoutError, ValueError) as exc:
            return self._fireworks_fallback(task, reason=f"assessment_or_decision_failure:{type(exc).__name__}")

        if solver is None and self.tool_planner_provider is not None and is_tool_planner_candidate(task.input_text):
            try:
                planner_invocation = self.tool_planner_provider.plan_with_trace(task)
                tool_decision = run_validated_tool_plan(task, planner_invocation.plan)
            except (FunctionGemmaToolPlannerError, OSError, TimeoutError, ValueError) as exc:
                return self._fireworks_fallback(task, reason=f"tool_planner_failure:{type(exc).__name__}")
            if not tool_decision.accepted:
                return self._fireworks_fallback(task, reason=f"tool_planner_rejected:{tool_decision.reason}")
            tool_selection = EngineDecision(
                engine=Engine.DETERMINISTIC,
                reason="functiongemma_planned_verified_tool",
                feasible_engines=(Engine.DETERMINISTIC, Engine.FIREWORKS),
                probability_correct=1.0,
            )
            trace = RoutingTrace(
                task_id=task.id,
                assessment=invocation.assessment,
                features=features,
                predictions=tuple(predictions[engine] for engine in sorted(predictions, key=lambda item: item.value)),
                decision=tool_selection,
            )
            result = AnswerResult(
                id=task.id,
                answer=tool_decision.answer,
                route="functiongemma_tool_verified",
                remote_tokens=TokenUsage.empty(),
                metadata={
                    "runner": "three_route",
                    "assessment_invocation": invocation.to_dict(),
                    "robust_selection": selection.to_dict(),
                    "tool_planner_invocation": planner_invocation.to_dict(),
                    "tool_decision": tool_decision.to_dict(),
                    "routing_trace": trace.to_dict(),
                },
            )
            self._log(task, result, trace)
            return result

        decision = selection.decision
        if solver is None and matrix_decision is not None and matrix_decision.probe:
            decision = EngineDecision(
                engine=Engine.GEMMA_E2B,
                reason="per_intent_matrix_probe",
                feasible_engines=(Engine.GEMMA_E2B, Engine.FIREWORKS),
                probability_correct=matrix_decision.probability,
            )
        fallback: str | None = None
        selective_probe = (
            self.selective_policy.should_probe(features)
            if self.selective_policy is not None and decision.engine is not Engine.DETERMINISTIC
            else None
        )
        extra_trees_probe = (
            self.extra_trees_gate.should_probe(invocation.raw_assessment.intent)
            if self.extra_trees_gate is not None and decision.engine is not Engine.DETERMINISTIC
            else False
        )
        if decision.engine is Engine.DETERMINISTIC:
            if solver is None:
                return self._fireworks_fallback(task, reason="selected_solver_did_not_accept_task")
            candidate = _solver_result(task, solver)
        elif decision.engine is Engine.GEMMA_E2B or (selective_probe is not None and selective_probe.probe) or extra_trees_probe:
            try:
                candidate = self.e2b_runner.run(task)
                validation = validate_or_safely_repair_final_answer(task, candidate.answer)
                retry = getattr(self.e2b_runner, "retry", None)
                elapsed_ms = round((monotonic() - started) * 1000)
                if (
                    candidate.route != "e2b_error"
                    and not validation.valid
                    and callable(retry)
                    and elapsed_ms <= self.e2b_retry_latest_start_ms
                ):
                    retried = retry(task)
                    retried_validation = validate_or_safely_repair_final_answer(task, retried.answer)
                    if retried.route != "e2b_error" and retried_validation.valid:
                        candidate = retried
                        validation = retried_validation
                extra_trees_decision = (
                    self.extra_trees_gate.evaluate(task, invocation.raw_assessment, candidate.answer)
                    if extra_trees_probe and self.extra_trees_gate is not None
                    else None
                )
                selective_decision = (
                    self.selective_policy.evaluate(task, candidate.answer, features)
                    if self.selective_policy is not None
                    else None
                )
                if candidate.route == "e2b_error":
                    fallback = "e2b_rejected:runtime_error"
                    candidate = self.fireworks_runner.run(task)
                elif extra_trees_decision is not None and not extra_trees_decision.accepted:
                    fallback = f"e2b_extra_trees_rejected:{extra_trees_decision.reason}"
                    candidate = self.fireworks_runner.run(task)
                elif extra_trees_decision is not None:
                    candidate = AnswerResult(
                        id=candidate.id,
                        answer=extra_trees_decision.answer,
                        route="e2b_local_extra_trees",
                        remote_tokens=candidate.remote_tokens,
                        metadata={
                            **candidate.metadata,
                            "e2b_extra_trees": {
                                "probability": extra_trees_decision.probability,
                                "accepted": True,
                                "reason": extra_trees_decision.reason,
                                "contract_valid": extra_trees_decision.contract_valid,
                            },
                        },
                    )
                    decision = EngineDecision(
                        engine=Engine.GEMMA_E2B,
                        reason="post_response_extra_trees_accept",
                        feasible_engines=(Engine.GEMMA_E2B, Engine.FIREWORKS),
                        probability_correct=extra_trees_decision.probability,
                    )
                elif selective_decision is not None and not selective_decision.accepted:
                    fallback = f"e2b_selective_rejected:{selective_decision.reason}"
                    candidate = self.fireworks_runner.run(task)
                elif selective_decision is None and not validation.valid:
                    fallback = f"e2b_rejected:{validation.reason}"
                    candidate = self.fireworks_runner.run(task)
                elif selective_decision is not None:
                    candidate = AnswerResult(
                        id=candidate.id,
                        answer=selective_decision.answer,
                        route="e2b_local_selective",
                        remote_tokens=candidate.remote_tokens,
                        metadata={**candidate.metadata, "selective_e2b": selective_decision.to_dict()},
                    )
                    decision = EngineDecision(
                        engine=Engine.GEMMA_E2B,
                        reason="post_response_selective_accept",
                        feasible_engines=(Engine.GEMMA_E2B, Engine.FIREWORKS),
                        probability_correct=selective_decision.post_probability,
                    )
                elif validation.repaired_answer:
                    candidate = AnswerResult(
                        id=candidate.id,
                        answer=validation.repaired_answer,
                        route="e2b_local_repaired",
                        remote_tokens=candidate.remote_tokens,
                        metadata={
                            **candidate.metadata,
                            "mechanical_repair": validation.to_dict(),
                        },
                    )
            except (MemoryError, OSError, RuntimeError, TimeoutError, ValueError) as exc:
                fallback = f"e2b_runtime_failure:{type(exc).__name__}"
                candidate = self.fireworks_runner.run(task)
        else:
            candidate = self.fireworks_runner.run(task)

        trace = RoutingTrace(
            task_id=task.id,
            assessment=invocation.assessment,
            features=features,
            predictions=tuple(predictions[engine] for engine in sorted(predictions, key=lambda item: item.value)),
            decision=decision,
            fallback=fallback,
        )
        metadata = dict(candidate.metadata)
        metadata.update(
            {
                "runner": "three_route",
                "assessment_invocation": invocation.to_dict(),
                "robust_selection": selection.to_dict(),
                "e2b_matrix": matrix_decision.__dict__ if matrix_decision else None,
                "risk_ladder": risk_decision.to_dict() if risk_decision else None,
                "selective_probe": selective_probe.to_dict() if selective_probe else None,
                "routing_trace": trace.to_dict(),
            }
        )
        result = AnswerResult(
            id=candidate.id,
            answer=candidate.answer,
            route=candidate.route,
            remote_tokens=candidate.remote_tokens,
            metadata=metadata,
        )
        self._log(task, result, trace)
        return result

    def _predictions(self, task: TaskEnvelope, features, solver: SolverResult | None) -> dict[Engine, EnginePrediction]:
        planned_model = getattr(self.fireworks_runner, "planned_model", None)
        if callable(planned_model):
            model_id = str(planned_model(task))
            try:
                fireworks_prediction = self.predictor.predict_fireworks_model(features, model_id)
            except ValueError:
                fireworks_prediction = self.predictor.predict(features, Engine.FIREWORKS)
        else:
            fireworks_prediction = self.predictor.predict(features, Engine.FIREWORKS)
        return {
            Engine.DETERMINISTIC: deterministic_solver_prediction(accepted=solver is not None),
            Engine.GEMMA_E2B: self.predictor.predict(features, Engine.GEMMA_E2B),
            Engine.FIREWORKS: fireworks_prediction,
        }

    def _fireworks_fallback(self, task: TaskEnvelope, *, reason: str) -> AnswerResult:
        candidate = self.fireworks_runner.run(task)
        decision = EngineDecision.fireworks_safe_fallback(reason)
        trace = RoutingTrace(
            task_id=task.id,
            assessment=None,
            features=None,
            predictions=(),
            decision=decision,
            fallback=reason,
        )
        result = AnswerResult(
            id=candidate.id,
            answer=candidate.answer,
            route=candidate.route,
            remote_tokens=candidate.remote_tokens,
            metadata={**candidate.metadata, "runner": "three_route", "routing_trace": trace.to_dict()},
        )
        self._log(task, result, trace)
        return result

    def _log(self, task: TaskEnvelope, result: AnswerResult, trace: RoutingTrace) -> None:
        if self.logger:
            metadata = result.metadata
            self.logger.log_result(
                task,
                result,
                extra={
                    "stage": "three_route",
                    "routing_trace": trace.to_dict(),
                    "fireworks_model": metadata.get("fireworks_model"),
                    "latency_fireworks_ms": int(metadata.get("latency_fireworks_ms") or 0),
                    "fireworks_request_options": metadata.get("fireworks_request_options") or {},
                    "e2b_matrix": metadata.get("e2b_matrix"),
                    "risk_ladder": metadata.get("risk_ladder"),
                    "selective_e2b": metadata.get("selective_e2b"),
                },
            )


def _solver_result(task: TaskEnvelope, solver: SolverResult) -> AnswerResult:
    return AnswerResult(
        id=task.id,
        answer=solver.answer,
        route=solver.route,
        remote_tokens=TokenUsage.empty(),
        metadata={"runner": "three_route_solver", "solver": solver.to_dict()},
    )
