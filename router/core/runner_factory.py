from __future__ import annotations

from router.core.config import RouterConfig
from router.core.local_runner import LocalM1Runner
from router.core.logging import JsonlRunLogger
from router.core.mock_runner import MockCascadeRunner
from router.core.model_client import LocalModelClient
from router.core.runner import TaskRunner


def build_runner(config: RouterConfig, logger: JsonlRunLogger) -> TaskRunner:
    mode = config.mode.lower()
    if mode == "mock":
        return MockCascadeRunner(logger=logger)
    if mode == "auto":
        if config.local_base_url and config.local_model:
            return _build_local_runner(config, logger)
        return MockCascadeRunner(logger=logger)
    if mode == "local":
        return _build_local_runner(config, logger)
    raise ValueError(f"Unsupported ROUTER_MODE: {config.mode}")


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

