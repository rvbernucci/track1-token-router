from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.fireworks import FireworksClient
from router.core.model_client import ModelClientError


DEFAULT_BASE_URL = "https://api.fireworks.ai/inference/v1"
DEFAULT_PROMPT = "Answer with exactly one word: ready"
DEFAULT_ENV_FILES = (Path(".env.fireworks"), Path(".env.fireworks.local"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a safe Fireworks chat-completions smoke test.")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--model", help="Override FIREWORKS_MODEL for this smoke test.")
    parser.add_argument("--allowed-models", help="Comma-separated model list; first item is used when --model is empty.")
    parser.add_argument("--base-url", help="Override FIREWORKS_BASE_URL.")
    parser.add_argument("--env-file", action="append", type=Path, help="Load KEY=VALUE pairs before running.")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--max-retries", type=int, default=0)
    parser.add_argument("--json", action="store_true", help="Emit a compact JSON result.")
    args = parser.parse_args()

    _load_env_files(tuple(args.env_file or DEFAULT_ENV_FILES))

    api_key = os.getenv("FIREWORKS_API_KEY")
    base_url = args.base_url or os.getenv("FIREWORKS_BASE_URL") or DEFAULT_BASE_URL
    allowed_models = _parse_models(args.allowed_models or os.getenv("ALLOWED_MODELS"))
    model = args.model or os.getenv("FIREWORKS_MODEL") or (allowed_models[0] if allowed_models else None)

    if not api_key:
        _print_missing("FIREWORKS_API_KEY is not set.")
        return 2
    if not model:
        _print_missing("FIREWORKS_MODEL or ALLOWED_MODELS is required.")
        return 2

    client = FireworksClient(
        base_url=base_url,
        model=model,
        api_key=api_key,
        timeout_s=args.timeout_s,
        max_retries=args.max_retries,
    )
    try:
        response = client.complete(
            [
                {
                    "role": "system",
                    "content": "You are running a connectivity smoke test. Reply briefly and do not include secrets.",
                },
                {"role": "user", "content": args.prompt},
            ],
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    except ModelClientError as exc:
        print(f"Fireworks smoke failed: {exc}", file=sys.stderr)
        return 1

    payload = {
        "ok": True,
        "base_url": base_url,
        "model": model,
        "usage": response.usage.to_dict(),
        "answer": response.text,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
    else:
        print("Fireworks smoke ok")
        print(f"base_url: {base_url}")
        print(f"model: {model}")
        print(f"tokens: {json.dumps(response.usage.to_dict(), sort_keys=True)}")
        print(f"answer: {response.text}")
    return 0


def _load_env_files(paths: tuple[Path, ...]) -> None:
    loaded_from_file: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            key, value = _parse_env_line(line)
            if not key:
                continue
            if key in os.environ and key not in loaded_from_file:
                continue
            os.environ[key] = value
            loaded_from_file.add(key)


def _parse_env_line(line: str) -> tuple[str | None, str]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None, ""
    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None, ""
    return key, _strip_quotes(value.strip())


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_models(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _print_missing(message: str) -> None:
    print(message, file=sys.stderr)
    print(
        "Load it with: set -a; . ./.env.fireworks; . ./.env.fireworks.local; set +a",
        file=sys.stderr,
    )
    print("This script never prints FIREWORKS_API_KEY.", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
