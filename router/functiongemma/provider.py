from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from router.core.contracts import TaskAssessment, TaskEnvelope, TokenUsage
from router.functiongemma.calibration import ScoreCalibrationBundle
from router.functiongemma.tooling import ASSESS_TASK_TOOL, DEVELOPER_INSTRUCTION, assessment_from_function_call


class FunctionGemmaProviderError(RuntimeError):
    pass


ASSESSMENT_PROMPT_VERSION = "functiongemma-tool-assessment-v1"


def build_assessment_messages(input_text: str) -> list[dict[str, str]]:
    return [
        {"role": "developer", "content": DEVELOPER_INSTRUCTION},
        {"role": "user", "content": input_text},
    ]


@dataclass(frozen=True)
class AssessmentInvocation:
    assessment: TaskAssessment
    raw_assessment: TaskAssessment
    latency_ms: float
    usage: TokenUsage
    model: str
    prompt_version: str = ASSESSMENT_PROMPT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment": self.assessment.to_dict(),
            "raw_assessment": self.raw_assessment.to_dict(),
            "latency_ms": self.latency_ms,
            "usage": self.usage.to_dict(),
            "model": self.model,
            "prompt_version": self.prompt_version,
        }


class FunctionGemmaAssessmentProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        calibration: ScoreCalibrationBundle,
        api_key: str | None = None,
        timeout_s: float = 10.0,
        max_tokens: int = 64,
        requester: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    ) -> None:
        if not base_url or not model or timeout_s <= 0 or not 1 <= max_tokens <= 256:
            raise ValueError("FunctionGemma provider configuration is invalid.")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.calibration = calibration
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self.requester = requester

    def assess(self, task: TaskEnvelope) -> TaskAssessment:
        return self.assess_with_trace(task).assessment

    def assess_with_trace(self, task: TaskEnvelope) -> AssessmentInvocation:
        payload = {
            "model": self.model,
            "messages": build_assessment_messages(task.input_text),
            "tools": [ASSESS_TASK_TOOL],
            "tool_choice": "required",
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "stop": ["<end_function_call>"],
        }
        started = time.monotonic()
        try:
            response = self.requester(payload) if self.requester else self._request(payload)
            raw = assessment_from_openai_response(response)
            calibrated = self.calibration.apply(raw)
        except (OSError, TimeoutError, ValueError, urllib.error.URLError) as exc:
            raise FunctionGemmaProviderError(str(exc)) from exc
        usage_payload = response.get("usage") if isinstance(response.get("usage"), Mapping) else {}
        usage = TokenUsage(
            prompt=_nonnegative_int(usage_payload.get("prompt_tokens")),
            completion=_nonnegative_int(usage_payload.get("completion_tokens")),
            total=_nonnegative_int(usage_payload.get("total_tokens")),
        )
        return AssessmentInvocation(
            assessment=calibrated,
            raw_assessment=raw,
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
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as result:
                response = json.load(result)
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            raise FunctionGemmaProviderError(f"FunctionGemma HTTP {status}") from exc
        if not isinstance(response, Mapping):
            raise ValueError("FunctionGemma response must be an object.")
        return response


def assessment_from_openai_response(payload: Mapping[str, Any]) -> TaskAssessment:
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
        raise ValueError("Assessment response must contain exactly one choice.")
    message = choices[0].get("message")
    if not isinstance(message, Mapping):
        raise ValueError("Assessment response choice is missing its message.")
    calls = message.get("tool_calls")
    if isinstance(calls, list) and calls:
        if len(calls) != 1 or not isinstance(calls[0], Mapping):
            raise ValueError("Assessment response must contain exactly one tool call.")
        function = calls[0].get("function")
        if not isinstance(function, Mapping) or function.get("name") != "assess_task":
            raise ValueError("Assessment response called an unexpected function.")
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        if not isinstance(arguments, Mapping):
            raise ValueError("Assessment tool arguments must be an object.")
        return TaskAssessment.from_mapping(arguments)
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("Assessment response has neither a tool call nor native-call content.")
    if content.startswith("<start_function_call>") and "<end_function_call>" not in content:
        content += "<end_function_call>"
    return assessment_from_function_call(content)


def _nonnegative_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0
