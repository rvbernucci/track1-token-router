import os
import unittest

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

    def test_fireworks_model_env_overrides_allowed_models(self) -> None:
        with patched_env(
            FIREWORKS_MODEL="accounts/fireworks/models/explicit",
            ALLOWED_MODELS="accounts/fireworks/models/first",
        ):
            config = RouterConfig.from_env()

        self.assertEqual(config.fireworks_model, "accounts/fireworks/models/explicit")

    def test_fireworks_service_tier_is_optional(self) -> None:
        with patched_env(FIREWORKS_SERVICE_TIER=None):
            default_config = RouterConfig.from_env()
        with patched_env(FIREWORKS_SERVICE_TIER="priority"):
            priority_config = RouterConfig.from_env()

        self.assertIsNone(default_config.fireworks_service_tier)
        self.assertEqual(priority_config.fireworks_service_tier, "priority")


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
