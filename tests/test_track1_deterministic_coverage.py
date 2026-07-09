import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.track1_deterministic_coverage import DEFAULT_DATASETS, build_report, render_markdown


class Track1DeterministicCoverageTests(unittest.TestCase):
    def test_default_microbenches_have_valid_deterministic_outputs(self) -> None:
        report = build_report(DEFAULT_DATASETS, min_coverage=0.40)

        self.assertTrue(report["ok"])
        self.assertEqual(report["invalid_deterministic_outputs"], [])
        self.assertGreaterEqual(report["totals"]["coverage_rate"], 0.40)
        self.assertEqual(report["totals"]["valid_deterministic_rate"], 1.0)
        self.assertTrue(all("non_deterministic_outputs" in row for row in report["datasets"]))

    def test_markdown_report_includes_routes_and_invalid_section(self) -> None:
        report = build_report(DEFAULT_DATASETS, min_coverage=0.40)

        markdown = render_markdown(report)

        self.assertIn("# Track 1 Deterministic Coverage", markdown)
        self.assertIn("solver_python_code_generation", markdown)
        self.assertIn("Invalid Deterministic Outputs", markdown)
        self.assertIn("Non-Deterministic Routes", markdown)
        self.assertIn("- none", markdown)

    def test_cli_check_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "coverage.md"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/track1_deterministic_coverage.py",
                    "--check",
                    "--report",
                    str(report_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn('"ok": true', completed.stdout)
            self.assertTrue(report_path.exists())


if __name__ == "__main__":
    unittest.main()
