import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from router.dev.fake_provider import SCENARIO_RESPONSES
from router.evals.bad_local_model import REQUIRED_PROFILES, run_bad_local_model_drill


class BadLocalModelChaosTests(unittest.TestCase):
    def test_fake_provider_exposes_required_bad_model_profiles(self) -> None:
        self.assertTrue(REQUIRED_PROFILES.issubset(set(SCENARIO_RESPONSES)))

    def test_bad_local_model_drill_contains_all_bad_candidates(self) -> None:
        report = run_bad_local_model_drill()

        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["metrics"]["false_approval_rate"], 0.0)
        self.assertEqual(report["metrics"]["containment_rate"], 1.0)
        self.assertEqual(set(report["metrics"]["profiles"]), REQUIRED_PROFILES)

    def test_bad_local_model_drill_exercises_repair_and_remote_dry_run(self) -> None:
        report = run_bad_local_model_drill()
        rows = {row["id"]: row for row in report["rows"]}

        self.assertTrue(rows["chaos_current_hallucination_001"]["remote_would_call"])
        self.assertTrue(rows["chaos_format_drift_001"]["validator_repaired"])
        self.assertTrue(rows["chaos_empty_refusal_001"]["local_repaired"])
        self.assertTrue(rows["chaos_wrong_math_001"]["local_repaired"])
        self.assertTrue(rows["chaos_prompt_injection_001"]["local_repaired"])

    def test_bad_local_model_drill_cli_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "bad-local-model-report.md"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/bad_local_model_drill.py",
                    "--check",
                    "--report",
                    str(report_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            content = report_path.read_text(encoding="utf-8")

        self.assertIn('"ok": true', completed.stdout)
        self.assertIn("Bad Local Model Chaos Report", content)


if __name__ == "__main__":
    unittest.main()
