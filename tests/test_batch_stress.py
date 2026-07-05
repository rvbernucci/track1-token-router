import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.batch_stress import DEFAULT_BATCH_PATH, run_batch_stress


class BatchStressTests(unittest.TestCase):
    def test_batch_fixture_has_one_thousand_tasks(self) -> None:
        lines = DEFAULT_BATCH_PATH.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 1000)
        self.assertEqual(json.loads(lines[0])["id"], "stress_0001")
        self.assertEqual(json.loads(lines[-1])["id"], "stress_1000")

    def test_batch_stress_passes_thresholds_and_preserves_contracts(self) -> None:
        report = run_batch_stress()

        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["large_batch"]["tasks"], 1000)
        self.assertTrue(report["large_batch"]["output_order_preserved"])
        self.assertEqual(report["cli_contract"]["output_contract_pass_rate"], 1.0)
        self.assertTrue(report["cli_contract"]["stdout_clean"])
        self.assertTrue(report["failure_probes"]["local_timeout_controlled"])
        self.assertTrue(report["failure_probes"]["intermittent_error_controlled"])
        self.assertTrue(report["failure_probes"]["remote_timeout_controlled"])

    def test_batch_stress_cli_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "batch-stress.md"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/batch_stress.py",
                    "--check",
                    "--report",
                    str(report_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            content = report_path.read_text(encoding="utf-8")

        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(completed.stderr, "")
        self.assertIn("Batch Stress Report", content)


if __name__ == "__main__":
    unittest.main()
