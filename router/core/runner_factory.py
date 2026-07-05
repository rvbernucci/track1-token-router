from __future__ import annotations

from router.core.config import RouterConfig
from router.core.fireworks import FireworksClient
from router.core.guardrails import GuardedRunner
from router.core.hybrid_cascade import HybridCascadeRunner
from router.core.local_cascade import LocalCascadeRunner
from router.core.local_runner import LocalM1Runner
from router.core.logging import JsonlRunLogger
from router.core.mock_runner import MockCascadeRunner
from router.core.model_client import LocalModelClient
from router.core.runner import TaskRunner


def build_runner(config: RouterConfig, logger: JsonlRunLogger) -> TaskRunner:
    mode = config.mode.lower()
    if mode == "mock":
        return _with_guardrails(MockCascadeRunner(logger=logger), config, logger)
    if mode == "auto":
        if config.local_base_url and config.local_model:
            return _with_guardrails(_build_local_runner(config, logger), config, logger)
        return _with_guardrails(MockCascadeRunner(logger=logger), config, logger)
    if mode == "local":
        return _with_guardrails(_build_local_runner(config, logger), config, logger)
    if mode == "cascade":
        return _with_guardrails(_build_local_cascade_runner(config, logger), config, logger)
    if mode == "hybrid":
        return _with_guardrails(_build_hybrid_cascade_runner(config, logger), config, logger)
    raise ValueError(f"Unsupported ROUTER_MODE: {config.mode}")


def _with_guardrails(runner: TaskRunner, config: RouterConfig, logger: JsonlRunLogger) -> TaskRunner:
    if config.enable_guardrails:
        return GuardedRunner(runner, logger=logger)
    return runner


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


def _build_local_cascade_runner(config: RouterConfig, logger: JsonlRunLogger) -> LocalCascadeRunner:
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
