from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RouterConfig:
    log_path: Path
    mode: str
    policy: str
    local_base_url: str | None
    local_model: str | None
    local_api_key: str | None
    local_timeout_s: float
    local_max_retries: int
    m1_temperature: float
    m1_max_tokens: int
    m2a_temperature: float
    m2a_max_tokens: int
    m2b_temperature: float
    m2b_max_tokens: int
    fireworks_base_url: str
    fireworks_model: str | None
    allowed_models: list[str]
    fireworks_api_key: str | None
    fireworks_timeout_s: float
    fireworks_max_retries: int
    fireworks_temperature: float
    fireworks_max_tokens: int
    fireworks_service_tier: str | None
    enable_guardrails: bool
    enable_orchestrator: bool
    competition_dry_run: bool
    max_remote_tokens_per_task: int
    max_remote_tokens_per_run: int
    max_remote_latency_ms: int

    @classmethod
    def from_env(cls) -> "RouterConfig":
        return cls(
            log_path=Path(os.getenv("ROUTER_LOG_PATH", "logs/run.jsonl")),
            mode=os.getenv("ROUTER_MODE", "mock"),
            policy=os.getenv("ROUTER_POLICY", "balanced"),
            local_base_url=os.getenv("LOCAL_BASE_URL"),
            local_model=os.getenv("LOCAL_MODEL"),
            local_api_key=os.getenv("LOCAL_API_KEY"),
            local_timeout_s=float(os.getenv("LOCAL_TIMEOUT_S", "30")),
            local_max_retries=int(os.getenv("LOCAL_MAX_RETRIES", "1")),
            m1_temperature=float(os.getenv("M1_TEMPERATURE", "0.2")),
            m1_max_tokens=int(os.getenv("M1_MAX_TOKENS", "512")),
            m2a_temperature=float(os.getenv("M2A_TEMPERATURE", "0.0")),
            m2a_max_tokens=int(os.getenv("M2A_MAX_TOKENS", "256")),
            m2b_temperature=float(os.getenv("M2B_TEMPERATURE", "0.2")),
            m2b_max_tokens=int(os.getenv("M2B_MAX_TOKENS", "768")),
            fireworks_base_url=os.getenv("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"),
            fireworks_model=os.getenv("FIREWORKS_MODEL") or _first_allowed_model(os.getenv("ALLOWED_MODELS")),
            allowed_models=_allowed_models(os.getenv("ALLOWED_MODELS")),
            fireworks_api_key=os.getenv("FIREWORKS_API_KEY"),
            fireworks_timeout_s=float(os.getenv("FIREWORKS_TIMEOUT_S", "60")),
            fireworks_max_retries=int(os.getenv("FIREWORKS_MAX_RETRIES", "1")),
            fireworks_temperature=float(os.getenv("FIREWORKS_TEMPERATURE", "0.0")),
            fireworks_max_tokens=int(os.getenv("FIREWORKS_MAX_TOKENS", "256")),
            fireworks_service_tier=os.getenv("FIREWORKS_SERVICE_TIER") or None,
            enable_guardrails=_env_flag("ENABLE_GUARDRAILS"),
            enable_orchestrator=_env_flag("ENABLE_ORCHESTRATOR"),
            competition_dry_run=_env_flag("COMPETITION_DRY_RUN", default=True),
            max_remote_tokens_per_task=int(os.getenv("MAX_REMOTE_TOKENS_PER_TASK", "300")),
            max_remote_tokens_per_run=int(os.getenv("MAX_REMOTE_TOKENS_PER_RUN", "6000")),
            max_remote_latency_ms=int(os.getenv("MAX_REMOTE_LATENCY_MS", "3000")),
        )


def _env_flag(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    return value in {"1", "true", "yes", "on"}


def _first_allowed_model(raw: str | None) -> str | None:
    models = _allowed_models(raw)
    return models[0] if models else None


def _allowed_models(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]
