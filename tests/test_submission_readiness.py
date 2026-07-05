import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.submission_readiness_check import check_submission_readiness


class SubmissionReadinessTests(unittest.TestCase):
    def test_checked_in_submission_readiness_is_ok(self) -> None:
        readiness = check_submission_readiness(Path("."))

        self.assertTrue(readiness.ok)
        self.assertEqual(readiness.errors, [])
        self.assertGreaterEqual(readiness.metrics["long_description_words"], 100)
        self.assertLessEqual(readiness.metrics["short_description_chars"], 255)

    def test_submission_readiness_cli_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "submission-readiness.md"
            completed = subprocess.run(
                [sys.executable, "scripts/submission_readiness_check.py", "--report", str(report)],
                check=True,
                capture_output=True,
                text=True,
            )

            content = report.read_text(encoding="utf-8")

        self.assertIn('"ok": true', completed.stdout)
        self.assertIn("Submission Readiness Report", content)

    def test_submission_readiness_fails_when_required_artifact_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            for relative in (
                "submission",
                ".github",
            ):
                shutil.copytree(relative, tmp_root / relative)
            for relative in (
                "README.md",
                "SUBMISSION.md",
                "CREDIT_ACTIVATION.md",
                "Dockerfile",
            ):
                shutil.copy2(relative, tmp_root / relative)
            (tmp_root / "submission" / "short-description.md").unlink()

            readiness = check_submission_readiness(tmp_root)

        self.assertFalse(readiness.ok)
        self.assertTrue(any("short-description.md" in error for error in readiness.errors))


if __name__ == "__main__":
    unittest.main()
