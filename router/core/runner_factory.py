from __future__ import annotations

from router.core.config import RouterConfig
from router.core.fireworks import FireworksClient
from router.core.fireworks_runner import FireworksDirectRunner
from router.core.guardrails import GuardedRunner
from router.core.hybrid_cascade import HybridCascadeRunner
from router.core.local_cascade import LocalCascadeRunner
from router.core.local_runner import LocalM1Runner
from router.core.logging import JsonlRunLogger
from router.core.mock_runner import MockCascadeRunner
from router.core.model_client import LocalModelClient
from router.core.runner import TaskRunner
from router.orchestration.budget import TaskBudget
from router.orchestration.competition import CompetitionRunner
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
    if mode == "cascade":
        return _wrap_runner(_build_local_cascade_runner(config, logger), config, logger)
    if mode == "hybrid":
        return _wrap_runner(_build_hybrid_cascade_runner(config, logger), config, logger)
    if mode == "fireworks":
        return _wrap_runner(_build_fireworks_direct_runner(config, logger), config, logger)
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
    if config.competition_dry_run or not (config.local_base_url and config.local_model):
        inner: TaskRunner = MockCascadeRunner(logger=None)
    else:
        inner = _build_local_cascade_runner(config, logger=None)
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


def _build_local_cascade_runner(config: RouterConfig, logger: JsonlRunLogger | None) -> LocalCascadeRunner:
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


def _build_hybrid_cascade_runner(config: RouterConfig, logger: JsonlRunLogger) -> HybridCascadeRunner:
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
    )


def _build_fireworks_direct_runner(config: RouterConfig, logger: JsonlRunLogger) -> FireworksDirectRunner:
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
    )
