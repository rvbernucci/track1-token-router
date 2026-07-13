import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_public_report import export_public_reports, sanitize_public_text


class PublicReportExportTests(unittest.TestCase):
    def test_generated_reports_export_to_public_and_demo_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generated_root = Path(tmp) / "reports" / "generated"
            public_root = Path(tmp) / "reports" / "public"
            demo_root = Path(tmp) / "demo-site"
            generated_root.mkdir(parents=True)
            for report_name in ("battle-report.md", "fuzz-report.md", "submission-readiness.md"):
                (generated_root / report_name).write_text(
                    f"# {report_name}\n\n- safe: true\n",
                    encoding="utf-8",
                )

            result = export_public_reports(
                generated_root=generated_root,
                public_root=public_root,
                demo_root=demo_root,
            )

            manifest = json.loads((public_root / "manifest.json").read_text(encoding="utf-8"))
            public_reports_exist = [
                (public_root / report_name).exists()
                for report_name in ("battle-report.md", "fuzz-report.md", "submission-readiness.md")
            ]
            demo_reports_exist = [
                (demo_root / "public-reports" / report_name).exists()
                for report_name in ("battle-report.md", "fuzz-report.md", "submission-readiness.md")
            ]

        self.assertTrue(result.ok, result.errors)
        self.assertGreaterEqual(len(result.exported), 3)
        self.assertTrue(manifest["safe_to_publish"])
        self.assertEqual(public_reports_exist, [True, True, True])
        self.assertEqual(demo_reports_exist, [True, True, True])

    def test_sanitizer_redacts_local_paths_and_private_ips(self) -> None:
        sanitized, counts = sanitize_public_text(
            "log=/Users/alice/project/run.jsonl host=192.168.1.44"
        )

        self.assertIn("[REDACTED_PATH]", sanitized)
        self.assertIn("[REDACTED_PRIVATE_IP]", sanitized)
        self.assertEqual(counts["absolute_paths"], 1)
        self.assertEqual(counts["private_ips"], 1)

    def test_export_blocks_synthetic_secret_and_private_hostname(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            generated_root = Path(tmp) / "generated"
            generated_root.mkdir()
            token = "sk" + "-" + ("A" * 24)
            (generated_root / "battle-report.md").write_text(
                f"token={token}\nhost=router.internal\n", encoding="utf-8"
            )
            (generated_root / "fuzz-report.md").write_text("ok\n", encoding="utf-8")
            (generated_root / "submission-readiness.md").write_text("ok\n", encoding="utf-8")

            result = export_public_reports(
                generated_root=generated_root,
                public_root=Path(tmp) / "public",
                demo_root=Path(tmp) / "demo",
            )

        self.assertFalse(result.ok)
        self.assertTrue(any("secret-like token" in error for error in result.errors))
        self.assertTrue(any("private hostname" in error for error in result.errors))

    def test_static_demo_links_to_public_reports_and_reproduction_commands(self) -> None:
        content = Path("demo-site/index.html").read_text(encoding="utf-8")

        self.assertIn("reports/public/final-hybrid-scorecard.md", content)
        self.assertIn("reports/public/final-pareto-calibration.md", content)
        self.assertIn("public-reports/fuzz-report.md", content)
        self.assertIn("submission/final/final-release-decision.json", content)
        self.assertIn("README.md", content)
        self.assertIn("SUBMISSION.md", content)
        self.assertIn("FunctionGemma", content)
        self.assertIn("docker pull --platform linux/amd64", content)
        self.assertIn("docker run --rm --platform linux/amd64", content)
        self.assertIn("v3.12.1-no-hardcoded-startup-sla", content)
        self.assertIn("84.2% / 4,198 tokens", content)
        self.assertIn("774 tests", content)
        self.assertIn("cat output/results.json", content)
        self.assertIn("solver_arithmetic", content)


if __name__ == "__main__":
    unittest.main()
