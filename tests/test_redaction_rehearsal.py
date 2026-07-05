import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.redact_logs import redact_logs
from scripts.submission_rehearsal import run_submission_rehearsal


class RedactionRehearsalTests(unittest.TestCase):
    def test_redaction_removes_sensitive_strings_and_long_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "raw.jsonl"
            public_root = root / "public"
            report = root / "redaction.md"
            trace_summary = root / "trace-summary.md"
            long_candidate = "candidate " * 80
            source.write_text(
                json.dumps(
                    {
                        "task_id": "sensitive",
                        "route": "m1_approved",
                        "answer_chars": 10,
                        "extra": {
                            "model_1_candidate_raw": long_candidate,
                            "path": "/Users/example/private/file.txt",
                            "host": "router.internal",
                            "ip": "192.168.1.10",
                            "env": "FIREWORKS_API_KEY=abcdefghijklmnopqrstuvwxyz",
                        },
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            result = redact_logs(
                logs=[str(source)],
                public_root=public_root,
                report_path=report,
                trace_summary_path=trace_summary,
                max_text_chars=80,
            )
            redacted = (public_root / "raw.redacted.jsonl").read_text(encoding="utf-8")

        self.assertTrue(result["ok"], result["errors"])
        self.assertIn("[REDACTED_LONG_TEXT", redacted)
        self.assertIn("[REDACTED_PATH]", redacted)
        self.assertIn("[REDACTED_PRIVATE_HOST]", redacted)
        self.assertIn("[REDACTED_PRIVATE_IP]", redacted)
        self.assertIn("[REDACTED_ENV_SECRET]", redacted)
        self.assertNotIn("/Users/example", redacted)
        self.assertNotIn("192.168.1.10", redacted)

    def test_redaction_cli_writes_public_trace_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "redaction.md"
            public_root = Path(tmp) / "traces"
            trace_summary = Path(tmp) / "trace-summary.md"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/redact_logs.py",
                    "--check",
                    "--report",
                    str(report),
                    "--public-root",
                    str(public_root),
                    "--trace-summary",
                    str(trace_summary),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(completed.stdout)
            trace_summary_exists = trace_summary.exists()

        self.assertTrue(payload["ok"])
        self.assertEqual(completed.stderr, "")
        self.assertTrue(trace_summary_exists)

    def test_submission_rehearsal_runs_under_five_minutes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "submission-rehearsal.md"
            result = run_submission_rehearsal(report_path=report)
            report_exists = report.exists()

        self.assertTrue(result["ok"], result["errors"])
        self.assertLessEqual(result["estimated_video_seconds"], 300)
        self.assertTrue(report_exists)


if __name__ == "__main__":
    unittest.main()
