from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from router.orchestration.fireworks_model_router import normalize_fireworks_model_id


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
    fireworks_champion_model: str | None
    fireworks_matrix_weights: Path | None
    fireworks_intent_policy: Path | None
    fireworks_intent_policy_sha256: str | None
    functiongemma_base_url: str
    functiongemma_model: str
    functiongemma_api_key: str | None
    functiongemma_timeout_s: float
    functiongemma_max_tokens: int
    functiongemma_calibration: Path | None
    functiongemma_calibration_sha256: str | None
    functiongemma_planner_base_url: str
    functiongemma_planner_model: str
    functiongemma_planner_api_key: str | None
    functiongemma_planner_timeout_s: float
    functiongemma_planner_max_tokens: int
    dual_functiongemma_policy: Path | None
    dual_functiongemma_policy_sha256: str | None
    e2b_base_url: str
    e2b_model: str
    e2b_api_key: str | None
    e2b_timeout_s: float
    e2b_max_tokens: int
    outcome_models_path: Path | None
    outcome_models_sha256: str | None
    e2b_route_policy: Path | None
    e2b_route_policy_sha256: str | None
    e2b_selective_policy: Path | None
    e2b_selective_policy_sha256: str | None
    e2b_matrix_policy: Path | None
    e2b_matrix_policy_sha256: str | None
    e2b_extra_trees_policy: Path | None
    e2b_extra_trees_policy_sha256: str | None
    risk_ladder_policy: Path | None
    risk_ladder_policy_sha256: str | None
    three_route_accuracy_gate: float
    three_route_max_failure: float
    three_route_max_memory_mb: float
    three_route_deadline_reserve_ms: float
    enable_guardrails: bool
    enable_orchestrator: bool
    competition_dry_run: bool
    max_remote_tokens_per_task: int
    max_remote_tokens_per_run: int
    max_remote_latency_ms: int
    enable_legacy_cascade_modes: bool = False

    @classmethod
    def from_env(cls) -> "RouterConfig":
        allowed_models = _allowed_models(os.getenv("ALLOWED_MODELS"))
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
            fireworks_model=_authorized_fireworks_model(os.getenv("FIREWORKS_MODEL"), allowed_models),
            allowed_models=allowed_models,
            fireworks_api_key=os.getenv("FIREWORKS_API_KEY"),
            fireworks_timeout_s=float(os.getenv("FIREWORKS_TIMEOUT_S", "24")),
            fireworks_max_retries=int(os.getenv("FIREWORKS_MAX_RETRIES", "0")),
            fireworks_temperature=float(os.getenv("FIREWORKS_TEMPERATURE", "0.0")),
            fireworks_max_tokens=int(os.getenv("FIREWORKS_MAX_TOKENS", "512")),
            fireworks_service_tier=os.getenv("FIREWORKS_SERVICE_TIER") or None,
            fireworks_champion_model=_optional_model(os.getenv("FIREWORKS_CHAMPION_MODEL")),
            fireworks_matrix_weights=_optional_path(os.getenv("FIREWORKS_MATRIX_WEIGHTS")),
            fireworks_intent_policy=_optional_path(os.getenv("FIREWORKS_INTENT_POLICY")),
            fireworks_intent_policy_sha256=os.getenv("FIREWORKS_INTENT_POLICY_SHA256") or None,
            functiongemma_base_url=os.getenv("FUNCTIONGEMMA_BASE_URL", "http://127.0.0.1:8091/v1"),
            functiongemma_model=os.getenv("FUNCTIONGEMMA_MODEL", "functiongemma-q8"),
            functiongemma_api_key=os.getenv("FUNCTIONGEMMA_API_KEY") or None,
            functiongemma_timeout_s=float(os.getenv("FUNCTIONGEMMA_TIMEOUT_S", "5")),
            functiongemma_max_tokens=int(os.getenv("FUNCTIONGEMMA_MAX_TOKENS", "64")),
            functiongemma_calibration=_optional_path(os.getenv("FUNCTIONGEMMA_CALIBRATION")),
            functiongemma_calibration_sha256=os.getenv("FUNCTIONGEMMA_CALIBRATION_SHA256") or None,
            functiongemma_planner_base_url=os.getenv("FUNCTIONGEMMA_PLANNER_BASE_URL", "http://127.0.0.1:8092/v1"),
            functiongemma_planner_model=os.getenv("FUNCTIONGEMMA_PLANNER_MODEL", "functiongemma-planner"),
            functiongemma_planner_api_key=os.getenv("FUNCTIONGEMMA_PLANNER_API_KEY") or None,
            functiongemma_planner_timeout_s=float(os.getenv("FUNCTIONGEMMA_PLANNER_TIMEOUT_S", "8")),
            functiongemma_planner_max_tokens=int(os.getenv("FUNCTIONGEMMA_PLANNER_MAX_TOKENS", "160")),
            dual_functiongemma_policy=_optional_path(os.getenv("DUAL_FUNCTIONGEMMA_POLICY")),
            dual_functiongemma_policy_sha256=os.getenv("DUAL_FUNCTIONGEMMA_POLICY_SHA256") or None,
            e2b_base_url=os.getenv("E2B_BASE_URL", "http://127.0.0.1:9379/v1"),
            e2b_model=os.getenv("E2B_MODEL", "gemma4-e2b"),
            e2b_api_key=os.getenv("E2B_API_KEY") or None,
            e2b_timeout_s=float(os.getenv("E2B_TIMEOUT_S", "30")),
            e2b_max_tokens=int(os.getenv("E2B_MAX_TOKENS", "96")),
            outcome_models_path=_optional_path(os.getenv("OUTCOME_MODELS_PATH")),
            outcome_models_sha256=os.getenv("OUTCOME_MODELS_SHA256") or None,
            e2b_route_policy=_optional_path(os.getenv("E2B_ROUTE_POLICY")),
            e2b_route_policy_sha256=os.getenv("E2B_ROUTE_POLICY_SHA256") or None,
            e2b_selective_policy=_optional_path(os.getenv("E2B_SELECTIVE_POLICY")),
            e2b_selective_policy_sha256=os.getenv("E2B_SELECTIVE_POLICY_SHA256") or None,
            e2b_matrix_policy=_optional_path(os.getenv("E2B_MATRIX_POLICY")),
            e2b_matrix_policy_sha256=os.getenv("E2B_MATRIX_POLICY_SHA256") or None,
            e2b_extra_trees_policy=_optional_path(os.getenv("E2B_EXTRA_TREES_POLICY")),
            e2b_extra_trees_policy_sha256=os.getenv("E2B_EXTRA_TREES_POLICY_SHA256") or None,
            risk_ladder_policy=_optional_path(os.getenv("RISK_LADDER_POLICY")),
            risk_ladder_policy_sha256=os.getenv("RISK_LADDER_POLICY_SHA256") or None,
            three_route_accuracy_gate=float(os.getenv("THREE_ROUTE_ACCURACY_GATE", "0.60")),
            three_route_max_failure=float(os.getenv("THREE_ROUTE_MAX_FAILURE", "0.15")),
            three_route_max_memory_mb=float(os.getenv("THREE_ROUTE_MAX_MEMORY_MB", "3584")),
            three_route_deadline_reserve_ms=float(os.getenv("THREE_ROUTE_DEADLINE_RESERVE_MS", "50000")),
            enable_guardrails=_env_flag("ENABLE_GUARDRAILS"),
            enable_orchestrator=_env_flag("ENABLE_ORCHESTRATOR"),
            competition_dry_run=_env_flag("COMPETITION_DRY_RUN", default=True),
            max_remote_tokens_per_task=int(os.getenv("MAX_REMOTE_TOKENS_PER_TASK", "300")),
            max_remote_tokens_per_run=int(os.getenv("MAX_REMOTE_TOKENS_PER_RUN", "6000")),
            max_remote_latency_ms=int(os.getenv("MAX_REMOTE_LATENCY_MS", "3000")),
            enable_legacy_cascade_modes=_env_flag("ENABLE_LEGACY_CASCADE_MODES"),
        )


def _env_flag(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    return value in {"1", "true", "yes", "on"}


def _authorized_fireworks_model(raw: str | None, allowed_models: list[str]) -> str | None:
    if allowed_models:
        requested = _optional_model(raw)
        return requested if requested in allowed_models else allowed_models[0]
    return _optional_model(raw)


def _allowed_models(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [normalize_fireworks_model_id(item) for item in _split_allowed_models(raw)]


def _split_allowed_models(raw: str) -> list[str]:
    stripped = raw.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, list):
            return [str(item).strip() for item in payload if str(item).strip()]
    return [item for item in re.split(r"[,\s]+", stripped) if item]


def _optional_model(raw: str | None) -> str | None:
    model = normalize_fireworks_model_id(raw)
    return model or None


def _optional_path(raw: str | None) -> Path | None:
    if raw is None or not raw.strip():
        return None
    return Path(raw.strip())
