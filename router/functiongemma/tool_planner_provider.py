from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from router.core.contracts import TaskEnvelope, TokenUsage
from router.core.tool_planner import ToolPlan
from router.functiongemma.tool_planner import (
    PLANNER_DEVELOPER_INSTRUCTION,
    planner_tools,
    tool_plan_from_openai_response,
)


PLANNER_PROMPT_VERSION = "functiongemma-native-tool-planner-v1"


class FunctionGemmaToolPlannerError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolPlannerInvocation:
    plan: ToolPlan
    latency_ms: float
    usage: TokenUsage
    model: str
    prompt_version: str = PLANNER_PROMPT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.to_dict(),
            "latency_ms": self.latency_ms,
            "usage": self.usage.to_dict(),
            "model": self.model,
            "prompt_version": self.prompt_version,
        }


class FunctionGemmaToolPlannerProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_s: float = 8.0,
        max_tokens: int = 160,
        requester: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    ) -> None:
        if not base_url or not model or timeout_s <= 0 or not 1 <= max_tokens <= 256:
            raise ValueError("FunctionGemma planner provider configuration is invalid.")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self.requester = requester

    def plan_with_trace(self, task: TaskEnvelope) -> ToolPlannerInvocation:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "developer", "content": PLANNER_DEVELOPER_INSTRUCTION},
                {"role": "user", "content": task.input_text},
            ],
            "tools": planner_tools(),
            "tool_choice": "required",
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "stop": ["<end_function_call>"],
        }
        started = time.monotonic()
        try:
            response = self.requester(payload) if self.requester else self._request(payload)
            plan = tool_plan_from_openai_response(response)
        except (OSError, TimeoutError, ValueError, urllib.error.URLError) as exc:
            raise FunctionGemmaToolPlannerError(str(exc)) from exc
        usage_payload = response.get("usage") if isinstance(response.get("usage"), Mapping) else {}
        usage = TokenUsage(
            prompt=_nonnegative_int(usage_payload.get("prompt_tokens")),
            completion=_nonnegative_int(usage_payload.get("completion_tokens")),
            total=_nonnegative_int(usage_payload.get("total_tokens")),
        )
        return ToolPlannerInvocation(
            plan=plan,
            latency_ms=(time.monotonic() - started) * 1000,
            usage=usage,
            model=self.model,
        )

    def _request(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        headers = {"Content-Type": "application/json", "User-Agent": "track1-token-router/0.1"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as result:
                response = json.load(result)
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            raise FunctionGemmaToolPlannerError(f"FunctionGemma planner HTTP {status}") from exc
        if not isinstance(response, Mapping):
            raise ValueError("FunctionGemma planner response must be an object.")
        return response


def _nonnegative_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0
