#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from router.evals.offline_dataset import SECRET_PATTERNS


PROFILE_REQUIREMENTS = {
    "amd-mi300x-vllm.env.example": {
        "runbook": "docs/RUNBOOK_VLLM_OPENAI.md",
        "required": {
            "ROUTER_MODE",
            "COMPETITION_DRY_RUN",
            "LOCAL_BASE_URL",
            "LOCAL_MODEL",
            "VLLM_MODEL",
            "VLLM_PORT",
        },
    },
    "amd-mi300x-sglang.env.example": {
        "runbook": "docs/RUNBOOK_SGLANG_OPENAI.md",
        "required": {
            "ROUTER_MODE",
            "COMPETITION_DRY_RUN",
            "LOCAL_BASE_URL",
            "LOCAL_MODEL",
            "SGLANG_MODEL",
            "SGLANG_PORT",
        },
    },
    "gemma-local.env.example": {
        "runbook": "docs/RUNBOOK_GEMMA.md",
        "required": {
            "ROUTER_MODE",
            "COMPETITION_DRY_RUN",
            "LOCAL_BASE_URL",
            "LOCAL_MODEL",
            "GEMMA_MODEL_FAMILY",
            "GEMMA_PROMPT_FORMAT",
        },
    },
    "fireworks-serverless.env.example": {
        "runbook": "docs/RUNBOOK_FIREWORKS.md",
        "required": {
            "ROUTER_MODE",
            "FIREWORKS_BASE_URL",
            "FIREWORKS_MODEL",
            "FIREWORKS_API_KEY",
        },
    },
}


SECRET_VALUE_PATTERNS = [
    *SECRET_PATTERNS,
    re.compile(r"(?im)^[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET)[ \t]*=[ \t]*[A-Za-z0-9_\-]{16,}"),
]


@dataclass(frozen=True)
class ProfileCheck:
    profile: Path
    errors: list[str]


def check_runtime_profiles(root: Path = Path("runtime-profiles")) -> list[ProfileCheck]:
    checks: list[ProfileCheck] = []
    for filename, requirements in PROFILE_REQUIREMENTS.items():
        path = root / filename
        errors: list[str] = []
        if not path.exists():
            checks.append(ProfileCheck(path, [f"missing {path}"]))
            continue
        content = path.read_text(encoding="utf-8")
        values = _parse_env(content, errors)
        _check_required_keys(filename, values, requirements["required"], errors)
        _check_source_runbook(content, str(requirements["runbook"]), errors)
        _check_runbook_exists(str(requirements["runbook"]), errors)
        _check_no_real_secret(content, errors)
        _check_safe_defaults(filename, values, errors)
        checks.append(ProfileCheck(path, errors))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate runtime profile examples without credentials.")
    parser.add_argument("--root", type=Path, default=Path("runtime-profiles"))
    args = parser.parse_args()

    checks = check_runtime_profiles(args.root)
    errors = [(check.profile, error) for check in checks for error in check.errors]
    if errors:
        for profile, error in errors:
            print(f"runtime profile error: {profile}: {error}", file=sys.stderr)
        return 1
    print(f"runtime profiles ok: {args.root}")
    return 0


def _parse_env(content: str, errors: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            errors.append(f"line {line_number} is not KEY=VALUE")
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Z0-9_]+", key):
            errors.append(f"line {line_number} invalid env key: {key}")
            continue
        if key in values:
            errors.append(f"duplicate env key: {key}")
        values[key] = value.strip()
    return values


def _check_required_keys(filename: str, values: dict[str, str], required: set[str], errors: list[str]) -> None:
    missing = sorted(required - set(values))
    for key in missing:
        errors.append(f"{filename} missing required key {key}")


def _check_source_runbook(content: str, expected: str, errors: list[str]) -> None:
    first_lines = "\n".join(content.splitlines()[:5])
    if f"Source runbook: {expected}" not in first_lines:
        errors.append(f"missing source runbook comment for {expected}")


def _check_runbook_exists(path: str, errors: list[str]) -> None:
    if not Path(path).exists():
        errors.append(f"referenced runbook does not exist: {path}")


def _check_no_real_secret(content: str, errors: list[str]) -> None:
    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(content):
            errors.append(f"secret-like value found: {pattern.pattern}")


def _check_safe_defaults(filename: str, values: dict[str, str], errors: list[str]) -> None:
    local_base_url = values.get("LOCAL_BASE_URL", "")
    if local_base_url and not local_base_url.startswith(("http://127.0.0.1", "http://localhost")):
        errors.append("LOCAL_BASE_URL must default to localhost/127.0.0.1 in examples")
    if filename.startswith("amd-mi300x") and values.get("COMPETITION_DRY_RUN") != "0":
        errors.append("AMD runtime profile must show COMPETITION_DRY_RUN=0 for credit activation")
    if filename == "fireworks-serverless.env.example":
        if values.get("ROUTER_MODE") != "fireworks":
            errors.append("Fireworks serverless profile must default to ROUTER_MODE=fireworks")
        if values.get("FIREWORKS_BASE_URL") != "https://api.fireworks.ai/inference/v1":
            errors.append("Fireworks base URL must be the OpenAI-compatible endpoint")
        if values.get("FIREWORKS_API_KEY"):
            errors.append("FIREWORKS_API_KEY must be empty in example profile")
        if values.get("FIREWORKS_MAX_RETRIES") not in {"0", ""}:
            errors.append("Fireworks serverless profile should default to FIREWORKS_MAX_RETRIES=0")


if __name__ == "__main__":
    raise SystemExit(main())
