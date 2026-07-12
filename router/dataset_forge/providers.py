from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from router.core.contracts import Intent, SUB_INTENTS_BY_INTENT
from router.core.fireworks import FireworksClient
from router.core.model_client import ModelClientError
from router.dataset_forge.contracts import ProviderProvenance, config_sha256, stable_id
from router.orchestration.fireworks_model_router import (
    _profile_for_model,
    normalize_fireworks_model_id,
    select_reasoning_effort,
)
from router.orchestration.assessment import approximate_token_count


CLAUDE_MODEL = "claude-sonnet-5"
AGY_MODEL = "Gemini 3.5 Flash (Medium)"
DEFAULT_FIREWORKS_TEACHER = "accounts/fireworks/models/minimax-m3"
DEFAULT_CODEX_JUDGE = "codex-subscription-default"


class ProviderError(RuntimeError):
    pass


class ProviderQuotaExhausted(ProviderError):
    pass


class ProviderBudgetExceeded(ProviderError):
    pass


@dataclass(frozen=True)
class ProviderInvocation:
    payload: dict[str, Any]
    provenance: ProviderProvenance


class ClaudeCodeProvider:
    def __init__(
        self,
        *,
        model: str = CLAUDE_MODEL,
        executable: str = "claude",
        timeout_s: float = 300.0,
    ) -> None:
        if model != CLAUDE_MODEL:
            raise ValueError(f"Claude dataset provider must pin {CLAUDE_MODEL!r}.")
        self.model = model
        self.executable = executable
        self.timeout_s = timeout_s
        self._auth: dict[str, Any] | None = None

    def invoke(self, *, prompt: str, response_schema: Mapping[str, Any], role: str) -> ProviderInvocation:
        auth = self._validated_subscription_auth()
        command_config = {
            "model": self.model,
            "permission_mode": "plan",
            "tools": [],
            "no_session_persistence": True,
            "output_format": "json",
            "role": role,
        }
        command = [
            self.executable,
            "-p",
            "--model",
            self.model,
            "--permission-mode",
            "plan",
            "--tools",
            "",
            "--no-session-persistence",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(response_schema, ensure_ascii=True, separators=(",", ":")),
            "--system-prompt",
            "Return only the requested structured data. Do not read files, browse, execute tools, or answer the tasks.",
            prompt,
        ]
        try:
            with tempfile.TemporaryDirectory(prefix="dataset-forge-claude-") as tmp:
                completed = subprocess.run(
                    command,
                    cwd=tmp,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s,
                    check=False,
                    env=_claude_subscription_env(),
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProviderError(f"Claude Code invocation failed: {exc}") from exc

        combined = f"{completed.stdout}\n{completed.stderr}".strip()
        if completed.returncode != 0:
            if _looks_like_quota_exhaustion(combined):
                raise ProviderQuotaExhausted(_redacted_error("Claude Pro usage window exhausted", combined))
            raise ProviderError(_redacted_error("Claude Code failed", combined))

        try:
            outer = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Claude Code returned malformed outer JSON: {exc}") from exc
        if not isinstance(outer, dict):
            raise ProviderError("Claude Code outer response must be an object.")
        if str(outer.get("subtype") or "") in {"error_max_turns", "error_during_execution"}:
            raise ProviderError(_redacted_error("Claude Code did not complete", completed.stdout))
        payload = _structured_payload(outer)
        usage = _claude_usage(outer, self.model)
        request_id = str(outer.get("uuid") or outer.get("session_id") or stable_id("claude", prompt))
        provenance = ProviderProvenance(
            provider="claude_code",
            model=self.model,
            role=role,
            auth_mode=f"{auth['authMethod']}:{auth['subscriptionType']}",
            usage_window=_usage_window_id(),
            prompt_tokens=usage["prompt"],
            completion_tokens=usage["completion"],
            total_tokens=usage["prompt"] + usage["completion"],
            equivalent_cost_usd=float(outer.get("total_cost_usd") or 0.0),
            billable_cost_usd=0.0,
            request_id=request_id,
            config_sha256=config_sha256(command_config),
        )
        return ProviderInvocation(payload=payload, provenance=provenance)

    def _validated_subscription_auth(self) -> dict[str, Any]:
        if self._auth is not None:
            return self._auth
        try:
            completed = subprocess.run(
                [self.executable, "auth", "status"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
                env=_claude_subscription_env(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProviderError(f"Unable to verify Claude Code authentication: {exc}") from exc
        if completed.returncode != 0:
            raise ProviderError("Claude Code authentication is unavailable.")
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderError("Claude Code authentication status is not JSON.") from exc
        if not isinstance(payload, dict):
            raise ProviderError("Claude Code authentication status must be an object.")
        if payload.get("authMethod") != "claude.ai" or payload.get("subscriptionType") not in {"pro", "max"}:
            raise ProviderError(
                "Claude Code must authenticate through a Claude Pro/Max subscription; Console/API auth is forbidden."
            )
        self._auth = payload
        return payload


class CodexProvider:
    def __init__(
        self,
        *,
        model: str = DEFAULT_CODEX_JUDGE,
        executable: str = "codex",
        timeout_s: float = 300.0,
    ) -> None:
        self.model = model
        self.executable = executable
        self.timeout_s = timeout_s

    def invoke(self, *, prompt: str, response_schema: Mapping[str, Any], role: str) -> ProviderInvocation:
        full_prompt = (
            "Return exactly one JSON object matching the supplied response schema. "
            "Do not use tools, read files, browse, or answer the quoted dataset tasks.\n\n"
            f"REQUEST:\n{prompt}"
        )
        command_config = {"model": self.model, "sandbox": "read-only", "ephemeral": True, "role": role}
        try:
            with tempfile.TemporaryDirectory(prefix="dataset-forge-codex-") as tmp:
                root = Path(tmp)
                schema_path = root / "schema.json"
                result_path = root / "result.json"
                schema_path.write_text(json.dumps(response_schema, ensure_ascii=True), encoding="utf-8")
                command = [
                    self.executable,
                    "exec",
                    "--ephemeral",
                    "--skip-git-repo-check",
                    "--sandbox",
                    "read-only",
                    "--output-schema",
                    str(schema_path),
                    "--output-last-message",
                    str(result_path),
                ]
                if self.model != DEFAULT_CODEX_JUDGE:
                    command.extend(["--model", self.model])
                command.append("-")
                completed = subprocess.run(
                    command,
                    cwd=root,
                    input=full_prompt,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s,
                    check=False,
                )
                result_text = result_path.read_text(encoding="utf-8") if result_path.is_file() else ""
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProviderError(f"Codex invocation failed: {exc}") from exc
        combined = f"{completed.stdout}\n{completed.stderr}".strip()
        if completed.returncode != 0:
            if _looks_like_quota_exhaustion(combined):
                raise ProviderQuotaExhausted(_redacted_error("Codex usage window exhausted", combined))
            raise ProviderError(_redacted_error("Codex failed", combined))
        payload = _parse_json_object(result_text, "Codex structured response")
        prompt_tokens = approximate_token_count(full_prompt)
        completion_tokens = approximate_token_count(result_text)
        request_id = stable_id("codex", self.model, role, full_prompt, result_text)
        provenance = ProviderProvenance(
            provider="codex",
            model=self.model,
            role=role,
            auth_mode="codex_subscription",
            usage_window=_usage_window_id(),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            equivalent_cost_usd=0.0,
            billable_cost_usd=0.0,
            request_id=request_id,
            config_sha256=config_sha256(command_config),
        )
        return ProviderInvocation(payload=payload, provenance=provenance)


class FireworksDatasetProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str = DEFAULT_FIREWORKS_TEACHER,
        timeout_s: float = 90.0,
        max_retries: int = 1,
        max_tokens: int = 8192,
    ) -> None:
        if not api_key:
            raise ValueError("FireworksDatasetProvider requires an API key.")
        self.model = normalize_fireworks_model_id(model)
        self.max_tokens = max_tokens
        self.client = FireworksClient(
            base_url=base_url,
            model=self.model,
            api_key=api_key,
            timeout_s=timeout_s,
            max_retries=max_retries,
            retry_sleep_s=1.0,
        )

    def estimate_upper_bound_usd(self, prompt: str) -> float:
        profile = _profile_for_model(self.model)
        prompt_tokens = approximate_token_count(prompt) + 80
        return (
            prompt_tokens * profile.input_price_per_mtok + self.max_tokens * profile.output_price_per_mtok
        ) / 1_000_000

    def invoke(self, *, prompt: str, response_schema: Mapping[str, Any], role: str) -> ProviderInvocation:
        messages = [
            {
                "role": "system",
                "content": (
                    "Return only one JSON object matching the supplied schema. Do not answer any dataset task. "
                    "Do not emit markdown or hidden reasoning."
                ),
            },
            {
                "role": "user",
                "content": f"RESPONSE_SCHEMA:\n{json.dumps(response_schema, ensure_ascii=True)}\n\nREQUEST:\n{prompt}",
            },
        ]
        request_options: dict[str, Any] = {
            "response_format": {"type": "json_object"},
            "user": "dataset-forge-v1",
        }
        reasoning_effort = select_reasoning_effort(self.model, "strong")
        if reasoning_effort:
            request_options["reasoning_effort"] = reasoning_effort
        try:
            response = self.client.complete(
                messages,
                temperature=0.2 if role == "generator" else 0.0,
                max_tokens=self.max_tokens,
                extra_body=request_options,
            )
        except ModelClientError as exc:
            message = str(exc)
            if _looks_like_quota_exhaustion(message):
                raise ProviderQuotaExhausted(_redacted_error("Fireworks quota exhausted", message)) from exc
            raise ProviderError(_redacted_error("Fireworks invocation failed", message)) from exc
        payload = _parse_json_object(response.text, "Fireworks structured response")
        profile = _profile_for_model(self.model)
        billable = (
            response.usage.prompt * profile.input_price_per_mtok
            + response.usage.completion * profile.output_price_per_mtok
        ) / 1_000_000
        raw_id = response.raw.get("id")
        request_id = str(raw_id or stable_id("fireworks", self.model, prompt, response.text))
        provenance = ProviderProvenance(
            provider="fireworks",
            model=self.model,
            role=role,
            auth_mode="api_key",
            usage_window=_usage_window_id(),
            prompt_tokens=response.usage.prompt,
            completion_tokens=response.usage.completion,
            total_tokens=response.usage.prompt + response.usage.completion,
            equivalent_cost_usd=billable,
            billable_cost_usd=billable,
            request_id=request_id,
            config_sha256=config_sha256(
                {
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "role": role,
                    "request_options": request_options,
                }
            ),
        )
        return ProviderInvocation(payload=payload, provenance=provenance)


class AntigravityProvider:
    def __init__(
        self,
        *,
        model: str = AGY_MODEL,
        executable: str = "agy",
        timeout_s: float = 180.0,
        expected_email: str,
        accounts_path: Path = Path.home() / ".gemini" / "google_accounts.json",
    ) -> None:
        if not expected_email:
            raise ValueError("AntigravityProvider.expected_email is required.")
        self.model = model
        self.executable = executable
        self.timeout_s = timeout_s
        self.expected_email = expected_email
        self.accounts_path = accounts_path
        self._model_verified = False

    def invoke(self, *, prompt: str, response_schema: Mapping[str, Any], role: str) -> ProviderInvocation:
        self._verify_model()
        full_prompt = (
            "Return exactly one JSON object matching RESPONSE_SCHEMA. Do not use markdown, tools, files, or web access. "
            "Do not answer the dataset tasks.\n\n"
            f"RESPONSE_SCHEMA:\n{json.dumps(response_schema, ensure_ascii=True, separators=(',', ':'))}\n\n"
            f"REQUEST:\n{prompt}"
        )
        command_config = {
            "model": self.model,
            "mode": "plan",
            "sandbox": True,
            "role": role,
        }
        command = [
            self.executable,
            "--print",
            full_prompt,
            "--model",
            self.model,
            "--mode",
            "plan",
            "--sandbox",
            "--print-timeout",
            f"{int(self.timeout_s)}s",
        ]
        try:
            with tempfile.TemporaryDirectory(prefix="dataset-forge-agy-") as tmp:
                completed = subprocess.run(
                    command,
                    cwd=tmp,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s + 10,
                    check=False,
                    env=_agy_account_env(),
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProviderError(f"Antigravity invocation failed: {exc}") from exc
        combined = f"{completed.stdout}\n{completed.stderr}".strip()
        if completed.returncode != 0:
            if _looks_like_quota_exhaustion(combined):
                raise ProviderQuotaExhausted(_redacted_error("Antigravity usage window exhausted", combined))
            raise ProviderError(_redacted_error("Antigravity failed", combined))
        payload = _parse_json_object(completed.stdout, "Antigravity structured response")
        prompt_tokens = approximate_token_count(full_prompt)
        completion_tokens = approximate_token_count(completed.stdout)
        request_id = stable_id("agy", self.model, role, full_prompt, completed.stdout)
        provenance = ProviderProvenance(
            provider="agy",
            model=self.model,
            role=role,
            auth_mode="antigravity_account",
            usage_window=_usage_window_id(),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            equivalent_cost_usd=0.0,
            billable_cost_usd=0.0,
            request_id=request_id,
            config_sha256=config_sha256(command_config),
        )
        return ProviderInvocation(payload=payload, provenance=provenance)

    def _verify_model(self) -> None:
        if self._model_verified:
            return
        self._verify_account()
        try:
            completed = subprocess.run(
                [self.executable, "models"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
                env=_agy_account_env(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProviderError(f"Unable to list Antigravity models: {exc}") from exc
        if completed.returncode != 0 or self.model not in completed.stdout.splitlines():
            raise ProviderError(f"Antigravity model {self.model!r} is unavailable.")
        self._model_verified = True

    def _verify_account(self) -> None:
        try:
            payload = json.loads(self.accounts_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProviderError(f"Unable to verify the active Antigravity account: {exc}") from exc
        active = payload.get("active") if isinstance(payload, dict) else None
        if active != self.expected_email:
            raise ProviderError("Active Antigravity account does not match DATASET_AGY_EXPECTED_EMAIL.")


def generation_response_schema(item_count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "minItems": item_count,
                "maxItems": item_count,
                "items": _proposal_item_schema(),
            }
        },
    }


def rating_response_schema(item_count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "minItems": item_count,
                "maxItems": item_count,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["example_id", "assessment", "rationales"],
                    "properties": {
                        "example_id": {"type": "string"},
                        "assessment": _assessment_schema(),
                        "rationales": _rationale_schema(),
                    },
                },
            }
        },
    }


def _proposal_item_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "target_id",
            "task_text",
            "assessment",
            "rationales",
            "template_family",
            "mutation_lineage",
            "language",
            "mutation_kind",
            "boundary_dimension",
            "boundary_anchor",
            "parent_id",
        ],
        "properties": {
            "target_id": {"type": "string"},
            "task_text": {"type": "string"},
            "assessment": _assessment_schema(),
            "rationales": _rationale_schema(),
            "template_family": {"type": "string"},
            "mutation_lineage": {"type": "string"},
            "language": {"type": "string"},
            "mutation_kind": {"type": "string"},
            "boundary_dimension": {"type": ["string", "null"]},
            "boundary_anchor": {"type": ["integer", "null"]},
            "parent_id": {"type": ["string", "null"]},
        },
    }


def _assessment_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["intent", "sub_intent", "scores"],
        "properties": {
            "intent": {"type": "string", "enum": [intent.value for intent in Intent]},
            "sub_intent": {
                "type": "string",
                "enum": [sub for values in SUB_INTENTS_BY_INTENT.values() for sub in values],
            },
            "scores": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "deterministic_fit",
                    "reasoning_demand",
                    "knowledge_uncertainty",
                    "generation_demand",
                    "format_complexity",
                ],
                "properties": {
                    name: {"type": "integer", "minimum": 0, "maximum": 10}
                    for name in (
                        "deterministic_fit",
                        "reasoning_demand",
                        "knowledge_uncertainty",
                        "generation_demand",
                        "format_complexity",
                    )
                },
            },
        },
    }


def _rationale_schema() -> dict[str, Any]:
    fields = (
        "deterministic_fit",
        "reasoning_demand",
        "knowledge_uncertainty",
        "generation_demand",
        "format_complexity",
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(fields),
        "properties": {name: {"type": "string"} for name in fields},
    }


def _structured_payload(outer: Mapping[str, Any]) -> dict[str, Any]:
    structured = outer.get("structured_output")
    if isinstance(structured, dict):
        return dict(structured)
    result = outer.get("result")
    if isinstance(result, dict):
        return dict(result)
    if isinstance(result, str):
        return _parse_json_object(result, "Claude structured result")
    raise ProviderError("Claude Code response did not contain structured output.")


def _parse_json_object(raw: str, label: str) -> dict[str, Any]:
    stripped = raw.strip()
    if stripped.startswith("```json") and stripped.endswith("```"):
        stripped = stripped[7:-3].strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        # Some structured-output endpoints append a second object or prose even
        # after producing a complete valid object. Preserve the first complete
        # envelope; its exact schema is still validated by the caller.
        try:
            payload, end = json.JSONDecoder().raw_decode(stripped)
        except json.JSONDecodeError:
            raise ProviderError(f"{label} is malformed JSON: {exc}") from exc
        if end <= 0:
            raise ProviderError(f"{label} is malformed JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProviderError(f"{label} must be an object.")
    return payload


def _claude_usage(outer: Mapping[str, Any], model: str) -> dict[str, int]:
    model_usage = outer.get("modelUsage")
    usage = model_usage.get(model) if isinstance(model_usage, dict) else None
    if not isinstance(usage, dict):
        generic = outer.get("usage")
        usage = generic if isinstance(generic, dict) else {}
    prompt = sum(
        int(usage.get(name) or 0)
        for name in ("inputTokens", "input_tokens", "cacheReadInputTokens", "cacheCreationInputTokens")
    )
    completion = int(usage.get("outputTokens") or usage.get("output_tokens") or 0)
    return {"prompt": prompt, "completion": completion}


def _claude_subscription_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"):
        env.pop(key, None)
    return env


def _agy_account_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
    ):
        env.pop(key, None)
    return env


def _looks_like_quota_exhaustion(text: str) -> bool:
    lowered = text.casefold()
    return any(
        marker in lowered
        for marker in (
            "usage limit",
            "rate limit",
            "quota",
            "resets at",
            "resets in",
            "credit balance",
            "resource exhausted",
            "429",
        )
    )


def _redacted_error(prefix: str, raw: str) -> str:
    compact = " ".join(raw.split())
    for marker in ("sk-ant-", "fw_"):
        if marker in compact:
            compact = compact.split(marker, 1)[0] + marker + "[redacted]"
    return f"{prefix}: {compact[:500]}"


def _usage_window_id() -> str:
    now = datetime.now(timezone.utc)
    bucket = (now.hour // 5) * 5
    return f"{now.date().isoformat()}T{bucket:02d}:00Z"


def provider_from_env(name: str, *, role: str, max_tokens: int = 8192):
    if name == "claude":
        return ClaudeCodeProvider()
    if name == "codex":
        return CodexProvider()
    if name == "fireworks":
        api_key = os.getenv("FIREWORKS_API_KEY")
        if not api_key:
            raise ProviderError("FIREWORKS_API_KEY is not set.")
        return FireworksDatasetProvider(
            api_key=api_key,
            base_url=os.getenv("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"),
            model=os.getenv("DATASET_FIREWORKS_MODEL", DEFAULT_FIREWORKS_TEACHER),
            max_tokens=max_tokens,
        )
    if name == "agy":
        expected_email = os.getenv("DATASET_AGY_EXPECTED_EMAIL")
        if not expected_email:
            raise ProviderError("DATASET_AGY_EXPECTED_EMAIL is required for Antigravity account pinning.")
        return AntigravityProvider(
            model=os.getenv("DATASET_AGY_MODEL", AGY_MODEL),
            expected_email=expected_email,
        )
    raise ValueError(f"Unknown dataset provider {name!r} for role {role!r}.")
