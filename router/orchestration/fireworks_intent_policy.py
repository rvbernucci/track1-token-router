from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from router.orchestration.fireworks_model_router import normalize_fireworks_model_id


DOMAIN_TO_TRACK1_INTENT: dict[str, str] = {
    "classification": "sentiment",
    "summarization": "summarization",
    "extraction": "ner",
    "logic": "logic_puzzle",
    "math_reasoning": "math_reasoning",
    "code_debug": "code_debugging",
    "code_generation": "code_generation",
    "current_factual": "factual_qa",
}


@dataclass(frozen=True)
class FireworksIntentPolicy:
    default_enabled: bool
    default_model: str
    intent_models: Mapping[str, str]
    allowed_models: frozenset[str]
    source_report_sha256: str

    @classmethod
    def load(cls, path: Path, *, expected_sha256: str | None = None) -> "FireworksIntentPolicy":
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValueError("Fireworks intent policy SHA-256 does not match the pinned digest.")
        payload = json.loads(raw)
        if not isinstance(payload, Mapping) or payload.get("schema_version") != "fireworks-intent-policy-v1":
            raise ValueError("Fireworks intent policy schema is invalid.")
        if payload.get("selection_split") != "validation" or payload.get("locked_test_used_for_selection") is not False:
            raise ValueError("Fireworks intent policy must be selected from validation only.")
        if not isinstance(payload.get("default_enabled"), bool):
            raise ValueError("Fireworks intent policy requires a boolean default_enabled field.")

        allowed_models = frozenset(_model_list(payload.get("allowed_models"), "allowed_models"))
        default_model = normalize_fireworks_model_id(_required_string(payload.get("default_model"), "default_model"))
        raw_intents = payload.get("intent_models")
        if not isinstance(raw_intents, Mapping) or not raw_intents:
            raise ValueError("Fireworks intent policy requires intent_models.")
        intent_models = {
            _required_string(intent, "intent"): normalize_fireworks_model_id(_required_string(model, "model"))
            for intent, model in raw_intents.items()
        }
        referenced = {default_model, *intent_models.values()}
        if not referenced.issubset(allowed_models):
            raise ValueError("Fireworks intent policy references a model outside allowed_models.")
        source = payload.get("source")
        if not isinstance(source, Mapping):
            raise ValueError("Fireworks intent policy requires source evidence.")
        source_sha = _required_sha256(source.get("comparison_report_sha256"))
        return cls(
            default_enabled=bool(payload["default_enabled"]),
            default_model=default_model,
            intent_models=intent_models,
            allowed_models=allowed_models,
            source_report_sha256=source_sha,
        )

    def select(self, *, domain: str, runtime_allowed_models: Sequence[str]) -> dict[str, Any] | None:
        if not self.default_enabled:
            return {
                "enabled": False,
                "domain": domain,
                "selection_rule": "validation_only_intent_policy",
                "reason": "locked_test_promotion_gate_failed",
                "source_report_sha256": self.source_report_sha256,
            }
        runtime_allowed = {
            normalize_fireworks_model_id(model)
            for model in runtime_allowed_models
            if normalize_fireworks_model_id(model)
        }
        intent = DOMAIN_TO_TRACK1_INTENT.get(domain)
        preferred = self.intent_models.get(intent, self.default_model) if intent else self.default_model
        if preferred not in runtime_allowed:
            return {
                "enabled": True,
                "domain": domain,
                "intent": intent,
                "selection_rule": "validation_only_intent_policy",
                "reason": "preferred_model_not_runtime_allowed",
                "preferred_model": preferred,
                "source_report_sha256": self.source_report_sha256,
            }
        return {
            "enabled": True,
            "model": preferred,
            "domain": domain,
            "intent": intent,
            "selection_rule": "validation_only_intent_policy",
            "used_default": intent is None or intent not in self.intent_models,
            "source_report_sha256": self.source_report_sha256,
        }


def _model_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"Fireworks intent policy requires a non-empty {field} list.")
    models = [normalize_fireworks_model_id(_required_string(item, field)) for item in value]
    if len(models) != len(set(models)):
        raise ValueError(f"Fireworks intent policy {field} contains duplicates.")
    return models


def _required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Fireworks intent policy field {field} must be a non-empty string.")
    return value.strip()


def _required_sha256(value: object) -> str:
    text = _required_string(value, "comparison_report_sha256").lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError("Fireworks intent policy source hash must be SHA-256.")
    return text
