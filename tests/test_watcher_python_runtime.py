import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATCHERS = (
    ROOT / "scripts" / "watch_e2b_regression_amd.sh",
    ROOT / "scripts" / "watch_fireworks_baselines.sh",
)
NEW_CLIS = (
    ROOT / "scripts" / "analyze_regression_learning_curve.py",
    ROOT / "scripts" / "audit_e2b_rescue_gate.py",
    ROOT / "scripts" / "merge_engine_judgments.py",
)


class WatcherPythonRuntimeTests(unittest.TestCase):
    def test_watchers_pin_modern_python_and_have_valid_shell_syntax(self):
        for watcher in WATCHERS:
            with self.subTest(watcher=watcher.name):
                source = watcher.read_text(encoding="utf-8")
                self.assertIn("PYTHON_BIN", source)
                self.assertIn("sys.version_info >= (3, 10)", source)
                completed = subprocess.run(
                    ["bash", "-n", str(watcher)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_new_analysis_clis_execute_as_scripts(self):
        for script in NEW_CLIS:
            with self.subTest(script=script.name):
                completed = subprocess.run(
                    ["python3", str(script), "--help"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
