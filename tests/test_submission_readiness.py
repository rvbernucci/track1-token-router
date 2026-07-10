import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.build_submission_artifacts import build_submission_artifacts
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

    def test_artifact_builder_creates_final_placeholders(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/build_submission_artifacts.py", "--check"],
            check=True,
            capture_output=True,
            text=True,
        )

        payload = completed.stdout
        self.assertIn('"ok": true', payload)
        self.assertTrue(Path("submission/final/slides.pdf").exists())
        self.assertTrue(Path("submission/final/cover.png").exists())
        self.assertTrue(Path("submission/final/demo.mp4").exists())
        self.assertTrue(Path("submission/final/lablab-submit-fields.md").exists())

    def test_checked_in_strict_mode_is_ok_with_local_demo_video(self) -> None:
        readiness = check_submission_readiness(Path("."), strict=True)

        self.assertTrue(readiness.ok, readiness.errors)
        self.assertIn("submission/final/demo.mp4", readiness.metrics["strict_video_files"])
        self.assertFalse(any("video placeholder" in warning for warning in readiness.warnings))
        self.assertFalse(any("dry-run evidence" in warning for warning in readiness.warnings))

    def test_pending_benchmark_warning_requires_complete_resource_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            shutil.copytree("submission", tmp_root / "submission")
            status_path = tmp_root / "submission" / "final" / "submission-status.json"
            status = json.loads(status_path.read_text(encoding="utf-8"))
            status["resource_gate"]["process_max_rss_mib"] = None
            status_path.write_text(json.dumps(status) + "\n", encoding="utf-8")
            for relative in (".github",):
                shutil.copytree(relative, tmp_root / relative)
            for relative in ("README.md", "SUBMISSION.md", "CREDIT_ACTIVATION.md", "Dockerfile"):
                shutil.copy2(relative, tmp_root / relative)

            readiness = check_submission_readiness(tmp_root)

        self.assertTrue(readiness.ok, readiness.errors)
        self.assertTrue(any("dry-run evidence" in warning for warning in readiness.warnings))

    def test_strict_mode_warns_when_only_video_placeholder_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            shutil.copytree("submission", tmp_root / "submission")
            demo_mp4 = tmp_root / "submission" / "final" / "demo.mp4"
            if demo_mp4.exists():
                demo_mp4.unlink()
            status_path = tmp_root / "submission" / "final" / "submission-status.json"
            status_path.write_text(
                status_path.read_text(encoding="utf-8")
                .replace('"video_file": "submission/final/demo.mp4"', '"video_file": ""')
                .replace('"video_placeholder_approved": false', '"video_placeholder_approved": true'),
                encoding="utf-8",
            )
            for relative in (
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

            readiness = check_submission_readiness(tmp_root, strict=True)

        self.assertTrue(readiness.ok, readiness.errors)
        self.assertTrue(any("video placeholder" in warning for warning in readiness.warnings))

    def test_strict_mode_flags_pending_public_urls_and_ci(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            shutil.copytree("submission", tmp_root / "submission")
            for relative in (
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
            status_path = tmp_root / "submission" / "final" / "submission-status.json"
            status_path.write_text(
                "{\n"
                '  "ci_status": "pending-final-green",\n'
                '  "demo_url": "",\n'
                '  "docker_image": "",\n'
                '  "image_audit_status": "pending",\n'
                '  "repo_url": "https://github.com/rvbernucci/track1-token-router",\n'
                '  "video_placeholder_approved": true,\n'
                '  "video_url": ""\n'
                "}\n",
                encoding="utf-8",
            )

            readiness = check_submission_readiness(tmp_root, strict=True)

        self.assertFalse(readiness.ok)
        self.assertTrue(any("demo_url" in error for error in readiness.errors))
        self.assertTrue(any("ci_status" in error for error in readiness.errors))
        self.assertTrue(any("docker_image" in error for error in readiness.errors))
        self.assertTrue(any("image_audit_status" in error for error in readiness.errors))

    def test_strict_mode_passes_with_final_status_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            shutil.copytree("submission", tmp_root / "submission")
            for relative in (
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
            status_path = tmp_root / "submission" / "final" / "submission-status.json"
            status_path.write_text(
                "{\n"
                '  "ci_status": "green",\n'
                '  "demo_url": "https://example.com/demo",\n'
                '  "docker_image": "ghcr.io/rvbernucci/track1-token-router:offline-rc-test",\n'
                '  "image_audit_status": "green",\n'
                '  "release_tag": "offline-rc-test",\n'
                '  "commit_sha": "abc123",\n'
                '  "repo_url": "https://github.com/rvbernucci/track1-token-router",\n'
                '  "video_placeholder_approved": true,\n'
                '  "video_url": ""\n'
                "}\n",
                encoding="utf-8",
            )
            build_submission_artifacts(tmp_root)

            readiness = check_submission_readiness(tmp_root, strict=True)

        self.assertTrue(readiness.ok, readiness.errors)

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
