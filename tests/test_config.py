import os
import unittest
from pathlib import Path

from router.cli.main import _validate_track1_runtime_environment
from router.core.config import RouterConfig


class RouterConfigTests(unittest.TestCase):
    def test_fireworks_model_falls_back_to_first_allowed_model(self) -> None:
        with patched_env(
            FIREWORKS_MODEL=None,
            ALLOWED_MODELS="accounts/fireworks/models/first, accounts/fireworks/models/second",
        ):
            config = RouterConfig.from_env()

        self.assertEqual(config.fireworks_model, "accounts/fireworks/models/first")
        self.assertEqual(
            config.allowed_models,
            ["accounts/fireworks/models/first", "accounts/fireworks/models/second"],
        )

    def test_allowed_models_rejects_unauthorized_local_override(self) -> None:
        with patched_env(
            FIREWORKS_MODEL="accounts/fireworks/models/explicit",
            ALLOWED_MODELS="accounts/fireworks/models/first",
        ):
            config = RouterConfig.from_env()

        self.assertEqual(config.fireworks_model, "accounts/fireworks/models/first")

    def test_allowed_models_accepts_authorized_override(self) -> None:
        with patched_env(
            FIREWORKS_MODEL="accounts/fireworks/models/second",
            ALLOWED_MODELS="accounts/fireworks/models/first,accounts/fireworks/models/second",
        ):
            config = RouterConfig.from_env()

        self.assertEqual(config.fireworks_model, "accounts/fireworks/models/second")

    def test_fireworks_service_tier_is_optional(self) -> None:
        with patched_env(FIREWORKS_SERVICE_TIER=None):
            default_config = RouterConfig.from_env()
        with patched_env(FIREWORKS_SERVICE_TIER="priority"):
            priority_config = RouterConfig.from_env()

        self.assertIsNone(default_config.fireworks_service_tier)
        self.assertEqual(priority_config.fireworks_service_tier, "priority")

    def test_fireworks_champion_model_is_normalized_and_optional(self) -> None:
        with patched_env(FIREWORKS_CHAMPION_MODEL=None):
            default_config = RouterConfig.from_env()
        with patched_env(FIREWORKS_CHAMPION_MODEL="kimi-k2p7-code"):
            champion_config = RouterConfig.from_env()

        self.assertIsNone(default_config.fireworks_champion_model)
        self.assertEqual(champion_config.fireworks_champion_model, "accounts/fireworks/models/kimi-k2p7-code")

    def test_short_allowed_model_names_are_normalized(self) -> None:
        with patched_env(
            FIREWORKS_MODEL=None,
            ALLOWED_MODELS="minimax-m3,kimi-k2p7-code,gemma-4-31b-it",
        ):
            config = RouterConfig.from_env()

        self.assertEqual(config.fireworks_model, "accounts/fireworks/models/minimax-m3")
        self.assertEqual(
            config.allowed_models,
            [
                "accounts/fireworks/models/minimax-m3",
                "accounts/fireworks/models/kimi-k2p7-code",
                "accounts/fireworks/models/gemma-4-31b-it",
            ],
        )

    def test_allowed_models_accept_whitespace_and_newlines(self) -> None:
        with patched_env(
            FIREWORKS_MODEL=None,
            ALLOWED_MODELS="minimax-m3\nkimi-k2p7-code gemma-4-31b-it",
        ):
            config = RouterConfig.from_env()

        self.assertEqual(
            config.allowed_models,
            [
                "accounts/fireworks/models/minimax-m3",
                "accounts/fireworks/models/kimi-k2p7-code",
                "accounts/fireworks/models/gemma-4-31b-it",
            ],
        )

    def test_allowed_models_accept_json_array(self) -> None:
        with patched_env(
            FIREWORKS_MODEL=None,
            ALLOWED_MODELS='["minimax-m3", "kimi-k2p7-code", "gemma-4-31b-it"]',
        ):
            config = RouterConfig.from_env()

        self.assertEqual(config.fireworks_model, "accounts/fireworks/models/minimax-m3")
        self.assertEqual(
            config.allowed_models,
            [
                "accounts/fireworks/models/minimax-m3",
                "accounts/fireworks/models/kimi-k2p7-code",
                "accounts/fireworks/models/gemma-4-31b-it",
            ],
        )

    def test_short_fireworks_model_name_is_normalized(self) -> None:
        with patched_env(
            FIREWORKS_MODEL="gemma-4-31b-it-nvfp4",
            ALLOWED_MODELS=None,
        ):
            config = RouterConfig.from_env()

        self.assertEqual(config.fireworks_model, "accounts/fireworks/models/gemma-4-31b-it-nvfp4")

    def test_fireworks_matrix_weights_is_optional_path(self) -> None:
        with patched_env(FIREWORKS_MATRIX_WEIGHTS=None):
            default_config = RouterConfig.from_env()
        with patched_env(FIREWORKS_MATRIX_WEIGHTS="reports/generated/weights.json"):
            calibrated_config = RouterConfig.from_env()

        self.assertIsNone(default_config.fireworks_matrix_weights)
        self.assertEqual(calibrated_config.fireworks_matrix_weights, Path("reports/generated/weights.json"))

    def test_fireworks_intent_policy_is_optional_and_pinnable(self) -> None:
        with patched_env(FIREWORKS_INTENT_POLICY=None, FIREWORKS_INTENT_POLICY_SHA256=None):
            default_config = RouterConfig.from_env()
        with patched_env(
            FIREWORKS_INTENT_POLICY="configs/fireworks-intent-policy-v1.json",
            FIREWORKS_INTENT_POLICY_SHA256="a" * 64,
        ):
            calibrated_config = RouterConfig.from_env()

        self.assertIsNone(default_config.fireworks_intent_policy)
        self.assertIsNone(default_config.fireworks_intent_policy_sha256)
        self.assertEqual(calibrated_config.fireworks_intent_policy, Path("configs/fireworks-intent-policy-v1.json"))
        self.assertEqual(calibrated_config.fireworks_intent_policy_sha256, "a" * 64)

    def test_fireworks_defaults_fit_track1_latency_envelope(self) -> None:
        with patched_env(FIREWORKS_TIMEOUT_S=None, FIREWORKS_MAX_RETRIES=None):
            config = RouterConfig.from_env()

        self.assertLess(config.fireworks_timeout_s, 30)
        self.assertEqual(config.fireworks_max_retries, 0)

    def test_official_remote_runtime_requires_all_harness_variables(self) -> None:
        with patched_env(
            ROUTER_MODE="fireworks",
            FIREWORKS_API_KEY="test-key",
            FIREWORKS_BASE_URL=None,
            ALLOWED_MODELS="minimax-m3",
            FIREWORKS_MODEL=None,
        ):
            config = RouterConfig.from_env()
            with self.assertRaisesRegex(ValueError, "FIREWORKS_BASE_URL"):
                _validate_track1_runtime_environment(config)

    def test_official_remote_runtime_accepts_harness_authorized_model(self) -> None:
        with patched_env(
            ROUTER_MODE="fireworks",
            FIREWORKS_API_KEY="test-key",
            FIREWORKS_BASE_URL="https://proxy.invalid/inference/v1",
            ALLOWED_MODELS="minimax-m3,kimi-k2p7-code",
            FIREWORKS_MODEL="not-allowed",
        ):
            config = RouterConfig.from_env()
            _validate_track1_runtime_environment(config)

        self.assertEqual(config.fireworks_model, "accounts/fireworks/models/minimax-m3")

    def test_official_local_runtime_does_not_require_fireworks_variables(self) -> None:
        with patched_env(
            ROUTER_MODE="local",
            FIREWORKS_API_KEY=None,
            FIREWORKS_BASE_URL=None,
            ALLOWED_MODELS=None,
        ):
            config = RouterConfig.from_env()
            _validate_track1_runtime_environment(config)


class patched_env:
    def __init__(self, **values: str | None) -> None:
        self.values = values
        self.previous: dict[str, str | None] = {}

    def __enter__(self) -> None:
        for key, value in self.values.items():
            self.previous[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def __exit__(self, *_exc: object) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
