from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from router.core.assessment_runner import AssessmentSafeModeRunner
from router.core.config import RouterConfig
from router.core.fireworks import FireworksClient
from router.core.fireworks_runner import FireworksDirectRunner
from router.core.e2b_runner import GemmaE2BRunner
from router.core.guardrails import GuardedRunner
from router.core.local_runner import LocalM1Runner
from router.core.logging import JsonlRunLogger
from router.core.mock_runner import MockCascadeRunner
from router.core.model_client import LocalModelClient
from router.core.runner import TaskRunner
from router.core.three_route_runner import ThreeRouteRunner
from router.functiongemma.calibration import load_calibration
from router.functiongemma.provider import FunctionGemmaAssessmentProvider
from router.orchestration.budget import TaskBudget
from router.orchestration.competition import CompetitionRunner
from router.orchestration.game_theory_selector import MinimaxRegretSelector, RobustSelectionConfig
from router.orchestration.outcome_models import OutcomeModelBundle, OutcomeModelPredictor
from router.orchestration.state_machine import OrchestratedRunner


def build_runner(config: RouterConfig, logger: JsonlRunLogger) -> TaskRunner:
    mode = config.mode.lower()
    if mode == "mock":
        return _wrap_runner(MockCascadeRunner(logger=logger), config, logger)
    if mode == "auto":
        if config.local_base_url and config.local_model:
            return _wrap_runner(_build_local_runner(config, logger), config, logger)
        return _wrap_runner(MockCascadeRunner(logger=logger), config, logger)
    if mode == "local":
        return _wrap_runner(_build_local_runner(config, logger), config, logger)
    if mode in {"cascade", "hybrid"}:
        if not config.enable_legacy_cascade_modes:
            raise ValueError(
                f"ROUTER_MODE={mode} is retired; use three_route or set "
                "ENABLE_LEGACY_CASCADE_MODES=1 only for historical regression tests."
            )
        return _wrap_runner(_build_legacy_cascade_runner(mode, config, logger), config, logger)
    if mode == "fireworks":
        return _wrap_runner(_build_fireworks_direct_runner(config, logger), config, logger)
    if mode == "three_route":
        return _build_three_route_runner(config, logger)
    if mode == "competition":
        return _build_competition_runner(config, logger)
    raise ValueError(f"Unsupported ROUTER_MODE: {config.mode}")


def _wrap_runner(runner: TaskRunner, config: RouterConfig, logger: JsonlRunLogger) -> TaskRunner:
    if config.enable_orchestrator:
        return OrchestratedRunner(runner, logger=logger, enable_guardrails=config.enable_guardrails)
    return _with_guardrails(runner, config, logger)


def _with_guardrails(runner: TaskRunner, config: RouterConfig, logger: JsonlRunLogger) -> TaskRunner:
    if config.enable_guardrails:
        return GuardedRunner(runner, logger=logger)
    return runner


def _build_competition_runner(config: RouterConfig, logger: JsonlRunLogger) -> CompetitionRunner:
    if config.competition_dry_run:
        inner: TaskRunner = MockCascadeRunner(logger=None)
    else:
        inner = _build_fireworks_direct_runner(config, logger=None)
    return CompetitionRunner(
        inner,
        logger=logger,
        budget=TaskBudget(
            max_remote_tokens_per_task=config.max_remote_tokens_per_task,
            max_remote_tokens_per_run=config.max_remote_tokens_per_run,
            max_remote_latency_ms=config.max_remote_latency_ms,
        ),
        policy=config.policy,
        dry_run=config.competition_dry_run,
    )


def _build_local_runner(config: RouterConfig, logger: JsonlRunLogger) -> LocalM1Runner:
    if not config.local_base_url:
        raise ValueError("LOCAL_BASE_URL is required when ROUTER_MODE=local.")
    if not config.local_model:
        raise ValueError("LOCAL_MODEL is required when ROUTER_MODE=local.")
    client = LocalModelClient(
        base_url=config.local_base_url,
        model=config.local_model,
        api_key=config.local_api_key,
        timeout_s=config.local_timeout_s,
        max_retries=config.local_max_retries,
    )
    return LocalM1Runner(
        client,
        logger=logger,
        temperature=config.m1_temperature,
        max_tokens=config.m1_max_tokens,
    )


def _build_local_cascade_runner(config: RouterConfig, logger: JsonlRunLogger | None):
    from router.core.local_cascade import LocalCascadeRunner

    if not config.local_base_url:
        raise ValueError("LOCAL_BASE_URL is required when ROUTER_MODE=cascade.")
    if not config.local_model:
        raise ValueError("LOCAL_MODEL is required when ROUTER_MODE=cascade.")
    client = LocalModelClient(
        base_url=config.local_base_url,
        model=config.local_model,
        api_key=config.local_api_key,
        timeout_s=config.local_timeout_s,
        max_retries=config.local_max_retries,
    )
    return LocalCascadeRunner(
        client,
        logger=logger,
        m1_temperature=config.m1_temperature,
        m1_max_tokens=config.m1_max_tokens,
        m2a_temperature=config.m2a_temperature,
        m2a_max_tokens=config.m2a_max_tokens,
        m2b_temperature=config.m2b_temperature,
        m2b_max_tokens=config.m2b_max_tokens,
        policy=config.policy,
    )


def _build_hybrid_cascade_runner(config: RouterConfig, logger: JsonlRunLogger):
    from router.core.hybrid_cascade import HybridCascadeRunner

    if not config.local_base_url:
        raise ValueError("LOCAL_BASE_URL is required when ROUTER_MODE=hybrid.")
    if not config.local_model:
        raise ValueError("LOCAL_MODEL is required when ROUTER_MODE=hybrid.")
    if not config.fireworks_model:
        raise ValueError("FIREWORKS_MODEL is required when ROUTER_MODE=hybrid.")
    if not config.fireworks_api_key:
        raise ValueError("FIREWORKS_API_KEY is required when ROUTER_MODE=hybrid.")

    local_client = LocalModelClient(
        base_url=config.local_base_url,
        model=config.local_model,
        api_key=config.local_api_key,
        timeout_s=config.local_timeout_s,
        max_retries=config.local_max_retries,
    )
    fireworks_client = FireworksClient(
        base_url=config.fireworks_base_url,
        model=config.fireworks_model,
        api_key=config.fireworks_api_key,
        timeout_s=config.fireworks_timeout_s,
        max_retries=config.fireworks_max_retries,
    )
    return HybridCascadeRunner(
        local_client,
        fireworks_client,
        logger=logger,
        m1_temperature=config.m1_temperature,
        m1_max_tokens=config.m1_max_tokens,
        m2a_temperature=config.m2a_temperature,
        m2a_max_tokens=config.m2a_max_tokens,
        m2b_temperature=config.m2b_temperature,
        m2b_max_tokens=config.m2b_max_tokens,
        fireworks_temperature=config.fireworks_temperature,
        fireworks_max_tokens=config.fireworks_max_tokens,
        policy=config.policy,
        allowed_models=config.allowed_models,
        fireworks_service_tier=config.fireworks_service_tier,
        matrix_weights_path=config.fireworks_matrix_weights,
    )


def _build_legacy_cascade_runner(mode: str, config: RouterConfig, logger: JsonlRunLogger) -> TaskRunner:
    if mode == "cascade":
        return _build_local_cascade_runner(config, logger)
    return _build_hybrid_cascade_runner(config, logger)


def _build_three_route_runner(config: RouterConfig, logger: JsonlRunLogger) -> TaskRunner:
    fallback = _build_fireworks_direct_runner(config, logger=None, enable_deterministic_solvers=False)
    required = {
        "functiongemma_calibration": config.functiongemma_calibration,
        "outcome_models_path": config.outcome_models_path,
        "e2b_route_policy": config.e2b_route_policy,
    }
    missing = [name for name, path in required.items() if path is None or not path.is_file()]
    if missing:
        return AssessmentSafeModeRunner(
            fallback,
            logger=logger,
            reason="missing_three_route_artifacts:" + ",".join(sorted(missing)),
        )
    try:
        calibration = load_calibration(
            config.functiongemma_calibration,  # type: ignore[arg-type]
            expected_sha256=config.functiongemma_calibration_sha256,
        )
        bundle = OutcomeModelBundle.load(
            config.outcome_models_path,  # type: ignore[arg-type]
            expected_sha256=config.outcome_models_sha256,
        )
        e2b_policy = _load_e2b_policy(
            config.e2b_route_policy,  # type: ignore[arg-type]
            expected_sha256=config.e2b_route_policy_sha256,
        )
        policy_limit = int(e2b_policy["baseline"]["output_tokens"])
        if config.e2b_max_tokens != policy_limit:
            raise ValueError("E2B runtime token ceiling differs from its pinned route policy.")
        observed_models = config.allowed_models or ([config.fireworks_model] if config.fireworks_model else [])
        predictor = OutcomeModelPredictor(
            bundle,
            allowed_models=observed_models,
            e2b_model_id=str(e2b_policy["baseline"]["model"]),
            e2b_combined_memory_mb=float(e2b_policy["decision_evidence"]["combined_local_vm_hwm_mib"]),
        )
        assessment_provider = FunctionGemmaAssessmentProvider(
            base_url=config.functiongemma_base_url,
            model=config.functiongemma_model,
            calibration=calibration,
            api_key=config.functiongemma_api_key,
            timeout_s=config.functiongemma_timeout_s,
            max_tokens=config.functiongemma_max_tokens,
        )
        e2b_client = LocalModelClient(
            base_url=config.e2b_base_url,
            model=config.e2b_model,
            api_key=config.e2b_api_key,
            timeout_s=config.e2b_timeout_s,
            max_retries=0,
        )
        selector = MinimaxRegretSelector(
            config=RobustSelectionConfig(
                accuracy_gate=config.three_route_accuracy_gate,
                max_runtime_failure=config.three_route_max_failure,
                max_peak_memory_mb=config.three_route_max_memory_mb,
                deadline_reserve_ms=config.three_route_deadline_reserve_ms,
            ),
            e2b_enabled=bool(e2b_policy["default_enabled"]),
        )
        return ThreeRouteRunner(
            assessment_provider=assessment_provider,
            predictor=predictor,
            selector=selector,
            e2b_runner=GemmaE2BRunner(e2b_client, max_tokens=config.e2b_max_tokens),
            fireworks_runner=fallback,
            logger=logger,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return AssessmentSafeModeRunner(
            fallback,
            logger=logger,
            reason=f"invalid_three_route_artifact:{type(exc).__name__}",
        )


def _load_e2b_policy(path, *, expected_sha256: str | None) -> Mapping[str, Any]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("E2B route policy SHA-256 does not match the pinned digest.")
    payload = json.loads(raw)
    if not isinstance(payload, Mapping) or payload.get("schema_version") != "e2b-route-policy-v1":
        raise ValueError("E2B route policy schema is invalid.")
    if not isinstance(payload.get("default_enabled"), bool):
        raise ValueError("E2B route policy requires a boolean default_enabled field.")
    baseline = payload.get("baseline")
    evidence = payload.get("decision_evidence")
    if not isinstance(baseline, Mapping) or not isinstance(evidence, Mapping):
        raise ValueError("E2B route policy is missing baseline or evidence.")
    return payload


def _build_fireworks_direct_runner(
    config: RouterConfig,
    logger: JsonlRunLogger | None,
    *,
    enable_deterministic_solvers: bool = True,
) -> FireworksDirectRunner:
    if not config.fireworks_model:
        raise ValueError("FIREWORKS_MODEL or ALLOWED_MODELS is required when ROUTER_MODE=fireworks.")
    if not config.fireworks_api_key:
        raise ValueError("FIREWORKS_API_KEY is required when ROUTER_MODE=fireworks.")
    client = FireworksClient(
        base_url=config.fireworks_base_url,
        model=config.fireworks_model,
        api_key=config.fireworks_api_key,
        timeout_s=config.fireworks_timeout_s,
        max_retries=config.fireworks_max_retries,
    )
    return FireworksDirectRunner(
        client,
        logger=logger,
        temperature=config.fireworks_temperature,
        max_tokens=config.fireworks_max_tokens,
        allowed_models=config.allowed_models,
        service_tier=config.fireworks_service_tier,
        champion_model=config.fireworks_champion_model,
        matrix_weights_path=config.fireworks_matrix_weights,
        intent_policy_path=config.fireworks_intent_policy,
        intent_policy_sha256=config.fireworks_intent_policy_sha256,
        enable_deterministic_solvers=enable_deterministic_solvers,
    )
