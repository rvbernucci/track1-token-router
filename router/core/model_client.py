from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from router.core.contracts import TokenUsage


class ModelClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelResponse:
    text: str
    usage: TokenUsage = field(default_factory=TokenUsage.empty)
    raw: dict[str, Any] = field(default_factory=dict)


class LocalModelClient:
    """Minimal OpenAI-compatible chat client for local inference servers."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_s: float = 30.0,
        max_retries: int = 1,
        retry_sleep_s: float = 0.2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.retry_sleep_s = retry_sleep_s

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        extra_body: dict[str, Any] | None = None,
    ) -> ModelResponse:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if extra_body:
            payload.update(extra_body)
        response = self._post_json("/chat/completions", payload)
        return _parse_chat_completion(response)

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=self._headers(),
            method="POST",
        )

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                    body = response.read().decode("utf-8")
                parsed = json.loads(body)
                if not isinstance(parsed, dict):
                    raise ModelClientError("Model response must be a JSON object.")
                return parsed
            except urllib.error.HTTPError as exc:
                last_error = ModelClientError(_format_http_error(exc))
                if attempt < self.max_retries:
                    time.sleep(self.retry_sleep_s)
                    continue
                break
            except (TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(self.retry_sleep_s)
                    continue
                break

        raise ModelClientError(str(last_error) if last_error else "Unknown model client error.")

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "track1-token-router/0.1",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def _parse_chat_completion(payload: dict[str, Any]) -> ModelResponse:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ModelClientError("Model response missing choices.")

    first = choices[0]
    if not isinstance(first, dict):
        raise ModelClientError("Model choice must be an object.")

    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = first.get("text")

    if not isinstance(content, str):
        raise ModelClientError("Model response missing text content.")

    usage_payload = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    usage = TokenUsage(
        prompt=int(usage_payload.get("prompt_tokens") or 0),
        completion=int(usage_payload.get("completion_tokens") or 0),
        total=int(usage_payload.get("total_tokens") or 0),
    )
    return ModelResponse(text=content, usage=usage, raw=payload)


def _format_http_error(exc: urllib.error.HTTPError) -> str:
    body = ""
    try:
        body = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:
        body = ""
    finally:
        exc.close()
    if body:
        body = _sanitize_error_body(body)
        if len(body) > 500:
            body = body[:500] + "...[truncated]"
        return f"HTTP {exc.code} {exc.reason}: {body}"
    return f"HTTP {exc.code} {exc.reason}"


def _sanitize_error_body(body: str) -> str:
    return re.sub(r"fw_[A-Za-z0-9_-]{8,}", "fw_[redacted]", body)
