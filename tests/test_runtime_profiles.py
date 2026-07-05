import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_runtime_profiles import PROFILE_REQUIREMENTS, check_runtime_profiles


class RuntimeProfileTests(unittest.TestCase):
    def test_checked_in_runtime_profiles_are_valid(self) -> None:
        checks = check_runtime_profiles(Path("runtime-profiles"))
        errors = [error for check in checks for error in check.errors]

        self.assertEqual(errors, [])
        self.assertEqual({check.profile.name for check in checks}, set(PROFILE_REQUIREMENTS))

    def test_runtime_profile_cli_succeeds(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/check_runtime_profiles.py"],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("runtime profiles ok", completed.stdout)
        self.assertEqual(completed.stderr.strip(), "")

    def test_runtime_profile_check_rejects_secret_like_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "runtime-profiles"
            root.mkdir()
            for filename, requirements in PROFILE_REQUIREMENTS.items():
                profile = root / filename
                runbook = requirements["runbook"]
                profile.write_text(
                    f"# Source runbook: {runbook}\n"
                    "ROUTER_MODE=competition\n"
                    "COMPETITION_DRY_RUN=0\n"
                    "LOCAL_BASE_URL=http://127.0.0.1:8000/v1\n"
                    "LOCAL_MODEL=local-gemma\n"
                    "FIREWORKS_BASE_URL=https://api.fireworks.ai/inference/v1\n"
                    "FIREWORKS_MODEL=accounts/fireworks/models/replace-me\n"
                    "FIREWORKS_API_KEY=\n"
                    "VLLM_MODEL=local-gemma\n"
                    "VLLM_PORT=8000\n"
                    "SGLANG_MODEL=local-gemma\n"
                    "SGLANG_PORT=30000\n"
                    "GEMMA_MODEL_FAMILY=Gemma\n"
                    "GEMMA_PROMPT_FORMAT=gemma4\n",
                    encoding="utf-8",
                )
            (root / "fireworks-serverless.env.example").write_text(
                "# Source runbook: docs/RUNBOOK_FIREWORKS.md\n"
                "ROUTER_MODE=hybrid\n"
                "LOCAL_BASE_URL=http://127.0.0.1:8000/v1\n"
                "LOCAL_MODEL=local-gemma\n"
                "FIREWORKS_BASE_URL=https://api.fireworks.ai/inference/v1\n"
                "FIREWORKS_MODEL=accounts/fireworks/models/replace-me\n"
                "FIREWORKS_API_KEY=THIS_IS_A_FAKE_SECRET_VALUE\n",
                encoding="utf-8",
            )

            checks = check_runtime_profiles(root)

        errors = [error for check in checks for error in check.errors]
        self.assertTrue(any("secret-like value" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
