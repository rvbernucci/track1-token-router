import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.fake_openai_server import FakeOpenAIServer


ROOT = Path(__file__).resolve().parents[1]


class FireworksSmokeScriptTests(unittest.TestCase):
    def test_smoke_uses_openai_compatible_endpoint(self) -> None:
        with FakeOpenAIServer(response_text="ready", prompt_tokens=9, completion_tokens=1) as server:
            env = {
                **os.environ,
                "FIREWORKS_API_KEY": "test-key",
                "FIREWORKS_BASE_URL": server.url,
                "FIREWORKS_MODEL": "fake-fireworks",
            }
            completed = subprocess.run(
                [sys.executable, "scripts/fireworks_smoke.py", "--json", "--max-retries", "0"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["model"], "fake-fireworks")
        self.assertEqual(payload["answer"], "ready")
        self.assertEqual(payload["usage"]["total"], 10)
        self.assertEqual(server.requests[0]["path"], "/v1/chat/completions")
        self.assertEqual(server.requests[0]["payload"]["model"], "fake-fireworks")

    def test_smoke_loads_env_file_without_printing_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeOpenAIServer(response_text="ready") as server:
            env_file = Path(tmp) / "fireworks.env"
            env_file.write_text(
                "\n".join(
                    [
                        "FIREWORKS_API_KEY=test-key",
                        f"FIREWORKS_BASE_URL={server.url}",
                        "ALLOWED_MODELS=fake-fireworks,other-fireworks",
                    ]
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/fireworks_smoke.py",
                    "--json",
                    "--env-file",
                    str(env_file),
                    "--max-retries",
                    "0",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                env=_without_fireworks_env(),
            )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["model"], "fake-fireworks")
        self.assertNotIn("test-key", completed.stdout)
        self.assertNotIn("test-key", completed.stderr)

    def test_local_env_file_overrides_empty_base_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, FakeOpenAIServer(response_text="ready") as server:
            root = Path(tmp)
            base_env = root / ".env.fireworks"
            local_env = root / ".env.fireworks.local"
            base_env.write_text(
                "\n".join(
                    [
                        f"FIREWORKS_BASE_URL={server.url}",
                        "FIREWORKS_API_KEY=",
                        "FIREWORKS_MODEL=replace-me",
                    ]
                ),
                encoding="utf-8",
            )
            local_env.write_text(
                "\n".join(
                    [
                        "FIREWORKS_API_KEY=test-key",
                        "FIREWORKS_MODEL=fake-fireworks",
                    ]
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/fireworks_smoke.py",
                    "--json",
                    "--env-file",
                    str(base_env),
                    "--env-file",
                    str(local_env),
                    "--max-retries",
                    "0",
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                env=_without_fireworks_env(),
            )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["model"], "fake-fireworks")
        self.assertEqual(payload["answer"], "ready")

    def test_missing_key_fails_safely(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/fireworks_smoke.py",
                "--model",
                "fake-fireworks",
                "--env-file",
                str(ROOT / "does-not-exist.env"),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            env=_without_fireworks_env(),
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("FIREWORKS_API_KEY is not set", completed.stderr)
        self.assertIn("never prints FIREWORKS_API_KEY", completed.stderr)


def _without_fireworks_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("FIREWORKS_API_KEY", "FIREWORKS_BASE_URL", "FIREWORKS_MODEL", "ALLOWED_MODELS"):
        env.pop(key, None)
    return env


if __name__ == "__main__":
    unittest.main()
