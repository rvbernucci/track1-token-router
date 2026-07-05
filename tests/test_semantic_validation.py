import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from router.evals.semantic_judge import LABELS, judge_answer, load_rubrics, run_semantic_eval
from router.core.contracts import TaskEnvelope


class SemanticValidationTests(unittest.TestCase):
    def test_semantic_eval_covers_all_labels(self) -> None:
        report = run_semantic_eval()

        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(set(report["metrics"]["labels"]), LABELS)
        self.assertTrue(all(count == 1 for count in report["metrics"]["labels"].values()))
        self.assertEqual(report["metrics"]["label_match_rate"], 1.0)

    def test_judge_accepts_open_answer_without_exact_match(self) -> None:
        rubric = load_rubrics()["semantic_explain_001"]
        task = TaskEnvelope(id="semantic_explain_001", input_text="Explain the token router.")

        judgment = judge_answer(task, rubric)

        self.assertEqual(judgment.label, "acceptable")
        self.assertFalse(judgment.exact_match)

    def test_judge_flags_format_unsafe_hallucinated_and_verbose_classes(self) -> None:
        rubrics = load_rubrics()

        cases = {
            "semantic_decision_json_001": "format_fail",
            "semantic_unsafe_001": "unsafe",
            "semantic_unstable_001": "hallucinated",
            "semantic_too_verbose_001": "too_verbose",
        }
        for task_id, expected_label in cases.items():
            with self.subTest(task_id=task_id):
                rubric = rubrics[task_id]
                task = TaskEnvelope(id=task_id, input_text="fixture")
                judgment = judge_answer(task, rubric)
                self.assertEqual(judgment.label, expected_label)

    def test_semantic_eval_cli_writes_report_and_clean_json_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "semantic-eval.md"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/run_semantic_eval.py",
                    "--check",
                    "--report",
                    str(report_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)
            content = report_path.read_text(encoding="utf-8")

        self.assertEqual(completed.stderr, "")
        self.assertTrue(payload["ok"])
        self.assertIn("Semantic Eval Report", content)


if __name__ == "__main__":
    unittest.main()
