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
    fireworks_base_url: str
    fireworks_model: str | None

    @classmethod
    def from_env(cls) -> "RouterConfig":
        return cls(
            log_path=Path(os.getenv("ROUTER_LOG_PATH", "logs/run.jsonl")),
            mode=os.getenv("ROUTER_MODE", "mock"),
            local_base_url=os.getenv("LOCAL_BASE_URL"),
            local_model=os.getenv("LOCAL_MODEL"),
            fireworks_base_url=os.getenv("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"),
            fireworks_model=os.getenv("FIREWORKS_MODEL"),
        )

