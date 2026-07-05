import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from router.adapters.io import load_jsonl_tasks
from router.evals.fuzz_dataset import run_fuzz_pack, validate_fuzz_dataset, write_fuzz_dataset


class FuzzPackTests(unittest.TestCase):
    def test_generated_fuzz_pack_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "evals" / "fuzz"
            fixtures = Path(tmp) / "fixtures" / "fuzz"

            write_fuzz_dataset(root, fixtures_root=fixtures)
            errors = validate_fuzz_dataset(root, fixtures_root=fixtures)

        self.assertEqual(errors, [])

    def test_checked_in_fuzz_pack_validates(self) -> None:
        errors = validate_fuzz_dataset(Path("evals/fuzz"), fixtures_root=Path("fixtures/fuzz"))

        self.assertEqual(errors, [])

    def test_fuzz_tasks_cover_alternate_input_fields_and_files(self) -> None:
        tasks = load_jsonl_tasks(Path("evals/fuzz/tasks.jsonl"))
        ids = {task.id: task for task in tasks}

        self.assertEqual(ids["fuzz_alt_question_001"].input_text, "What is 3 + 4? Return only the number.")
        self.assertEqual(ids["fuzz_file_txt_001"].files[0].name, "brief.txt")
        self.assertGreater(len(ids["fuzz_large_payload_001"].input_text), 1000)

    def test_run_fuzz_pack_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "fuzz-output.jsonl"
            report = Path(tmp) / "fuzz-report.md"

            summary = run_fuzz_pack(root=Path("evals/fuzz"), out_path=out, report_path=report)

            rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
            content = report.read_text(encoding="utf-8")

        self.assertTrue(summary["contract_success"])
        self.assertTrue(summary["traces_complete"])
        self.assertGreaterEqual(summary["exact_match_rate"], 0.9)
        self.assertEqual(len(rows), summary["tasks"])
        self.assertIn("Fuzz Eval Report", content)

    def test_invalid_jsonl_fixture_fails_with_controlled_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "router",
                    "run",
                    "--jsonl",
                    "fixtures/fuzz/invalid.jsonl",
                    "--out",
                    str(Path(tmp) / "out.jsonl"),
                ],
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout.strip(), "")
        self.assertIn("router error:", completed.stderr)

    def test_competition_stdout_stays_clean_for_fuzz_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["ROUTER_MODE"] = "competition"
            env["COMPETITION_DRY_RUN"] = "1"
            env["ROUTER_LOG_PATH"] = str(Path(tmp) / "run.jsonl")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "router",
                    "ask",
                    "Return exactly SAFE_OUTPUT and nothing else.",
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

        self.assertEqual(completed.stdout.strip(), "SAFE_OUTPUT")
        self.assertEqual(completed.stderr.strip(), "")


if __name__ == "__main__":
    unittest.main()
