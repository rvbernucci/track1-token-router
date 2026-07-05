import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_demo_site import check_demo_site


class DemoSiteTests(unittest.TestCase):
    def test_checked_in_demo_site_is_publishable(self) -> None:
        result = check_demo_site(Path("."), expected_url="https://rvbernucci.github.io/track1-token-router/")

        self.assertTrue(result.ok, result.errors)
        self.assertGreaterEqual(result.metrics["link_count"], 5)
        self.assertIn("public-reports/battle-report.md", result.metrics["required_public_reports_present"])

    def test_demo_site_cli_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "demo-site-check.md"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/check_demo_site.py",
                    "--check",
                    "--report",
                    str(report),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            content = report.read_text(encoding="utf-8")

        self.assertIn('"ok": true', completed.stdout)
        self.assertIn("Demo Site Check", content)

    def test_demo_site_rejects_missing_internal_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            demo = root / "demo-site"
            reports = demo / "public-reports"
            reports.mkdir(parents=True)
            (reports / "battle-report.md").write_text("ok", encoding="utf-8")
            (reports / "fuzz-report.md").write_text("ok", encoding="utf-8")
            (reports / "submission-readiness.md").write_text("ok", encoding="utf-8")
            (reports / "manifest.json").write_text("{}", encoding="utf-8")
            (demo / "index.html").write_text(
                '<a href="missing.md">missing</a>'
                '<a href="https://github.com/rvbernucci/track1-token-router/blob/main/README.md">README</a>'
                '<a href="https://github.com/rvbernucci/track1-token-router/blob/main/SUBMISSION.md">SUBMISSION</a>',
                encoding="utf-8",
            )

            result = check_demo_site(root, expected_url="https://example.com/demo")

        self.assertFalse(result.ok)
        self.assertTrue(any("does not exist" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
