import subprocess
import sys
import unittest

from scripts.local_model_envelope import estimate_envelope


class LocalModelEnvelopeTests(unittest.TestCase):
    def test_estimate_accepts_small_model_with_margin(self) -> None:
        estimate = estimate_envelope(model_size_mb=2800, runtime_overhead_mb=400, kv_cache_mb=256, safety_margin_mb=384)

        self.assertTrue(estimate.ok)
        self.assertGreaterEqual(estimate.headroom_mb, 0)

    def test_estimate_rejects_model_without_headroom(self) -> None:
        estimate = estimate_envelope(model_size_mb=3600, runtime_overhead_mb=512, kv_cache_mb=256, safety_margin_mb=384)

        self.assertFalse(estimate.ok)
        self.assertLess(estimate.headroom_mb, 0)

    def test_cli_check_returns_nonzero_when_over_budget(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/local_model_envelope.py",
                "--model-size-mb",
                "3600",
                "--check",
            ],
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('"ok": false', completed.stdout)


if __name__ == "__main__":
    unittest.main()
