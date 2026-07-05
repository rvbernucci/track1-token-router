import tempfile
import unittest
from pathlib import Path

from router.evals.battle_drill import run_battle_drill, write_battle_report_markdown


class BattleDrillTests(unittest.TestCase):
    def test_battle_drill_selects_candidate_and_reports_readiness(self) -> None:
        report = run_battle_drill(
            tasks_path=Path("evals/offline/tasks.jsonl"),
            expected_path=Path("evals/offline/expected.jsonl"),
            prompt_manifest=Path("prompts/manifest.json"),
            trace_logs=["fixtures/logs/sample-run.jsonl"],
        )

        self.assertEqual(report["candidate"]["policy"], "balanced")
        self.assertGreaterEqual(len(report["scoreboard"]["rows"]), 3)
        self.assertEqual(len(report["policy_ablation"]["profiles"]), 3)
        self.assertTrue(report["readiness"]["candidate_selected"])
        self.assertTrue(report["readiness"]["prompt_manifest_clean"])
        self.assertTrue(report["readiness"]["guardrails_probe_safe"])
        self.assertTrue(report["readiness"]["competition_mode_ready"])
        self.assertTrue(report["competition_probe"]["traces_complete"])

    def test_battle_report_markdown_is_written(self) -> None:
        report = run_battle_drill(
            tasks_path=Path("evals/offline/tasks.jsonl"),
            expected_path=Path("evals/offline/expected.jsonl"),
            prompt_manifest=Path("prompts/manifest.json"),
            trace_logs=["fixtures/logs/sample-run.jsonl"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "battle-report.md"
            write_battle_report_markdown(out, report)
            content = out.read_text(encoding="utf-8")

        self.assertIn("Battle Drill Report", content)
        self.assertIn("Adaptive Policy Ablation", content)
        self.assertIn("Competition Mode Probe", content)


if __name__ == "__main__":
    unittest.main()
