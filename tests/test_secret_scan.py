import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SecretScanTests(unittest.TestCase):
    def test_ignores_local_env_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env.fireworks.local").write_text(
                "FIREWORKS_API_KEY=" + _fake_fireworks_key() + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts/secret_scan.py")],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("secret scan ok", completed.stdout)

    def test_fails_on_secret_like_value_in_scanned_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "FIREWORKS_API_KEY=" + _fake_fireworks_key() + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts/secret_scan.py")],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("README.md", completed.stdout)


def _fake_fireworks_key() -> str:
    return "fw_" + ("A" * 24)


if __name__ == "__main__":
    unittest.main()
