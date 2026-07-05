from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RouterConfig:
    log_path: Path
    mode: str
    local_base_url: str | None
    local_model: str | None
    local_api_key: str | None
    local_timeout_s: float
    local_max_retries: int
    m1_temperature: float
    m1_max_tokens: int
    fireworks_base_url: str
    fireworks_model: str | None

    @classmethod
    def from_env(cls) -> "RouterConfig":
        return cls(
            log_path=Path(os.getenv("ROUTER_LOG_PATH", "logs/run.jsonl")),
            mode=os.getenv("ROUTER_MODE", "mock"),
            local_base_url=os.getenv("LOCAL_BASE_URL"),
            local_model=os.getenv("LOCAL_MODEL"),
            local_api_key=os.getenv("LOCAL_API_KEY"),
            local_timeout_s=float(os.getenv("LOCAL_TIMEOUT_S", "30")),
            local_max_retries=int(os.getenv("LOCAL_MAX_RETRIES", "1")),
            m1_temperature=float(os.getenv("M1_TEMPERATURE", "0.2")),
            m1_max_tokens=int(os.getenv("M1_MAX_TOKENS", "512")),
            fireworks_base_url=os.getenv("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"),
            fireworks_model=os.getenv("FIREWORKS_MODEL"),
        )
