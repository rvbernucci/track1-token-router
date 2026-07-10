import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from router.core.assessment_runner import AssessmentSafeModeRunner
from router.core.config import RouterConfig
from router.core.logging import JsonlRunLogger
from router.core.runner_factory import build_runner
from router.core.three_route_runner import ThreeRouteRunner


ENV = {
    "ROUTER_MODE": "three_route",
    "FIREWORKS_API_KEY": "test-key",
    "ALLOWED_MODELS": "minimax-m3,kimi-k2p7-code",
    "FUNCTIONGEMMA_CALIBRATION": "reports/generated/amd-pod-scale789/runs/lora_r16_scale789/gguf/q8-cap64-calibration.json",
    "FUNCTIONGEMMA_CALIBRATION_SHA256": "0078565ab90a6c93981e954d13daabdaa11a4535da9257eae03f3a034afcc1e1",
    "OUTCOME_MODELS_PATH": "configs/engine-outcome-models-v1.json",
    "OUTCOME_MODELS_SHA256": "927a64303501d43f3b509a8f48d397d372c4211f8347890827206e82bda60712",
    "E2B_ROUTE_POLICY": "configs/e2b-route-policy-v1.json",
    "E2B_ROUTE_POLICY_SHA256": "24607dda80f861ecde022987111302590b0e17a61842ad5b3e0b17302047c4ad",
}


class ThreeRouteFactoryTests(unittest.TestCase):
    def test_builds_operational_runner_from_pinned_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, ENV, clear=False):
            config = RouterConfig.from_env()
            runner = build_runner(config, JsonlRunLogger(Path(tmp) / "run.jsonl"))
        self.assertIsInstance(runner, ThreeRouteRunner)
        self.assertFalse(runner.selector.e2b_enabled)

    def test_bad_artifact_hash_fails_closed(self):
        env = {**ENV, "OUTCOME_MODELS_SHA256": "0" * 64}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, env, clear=False):
            config = RouterConfig.from_env()
            runner = build_runner(config, JsonlRunLogger(Path(tmp) / "run.jsonl"))
        self.assertIsInstance(runner, AssessmentSafeModeRunner)


if __name__ == "__main__":
    unittest.main()
