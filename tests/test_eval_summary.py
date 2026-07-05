import json
import tempfile
import unittest
from pathlib import Path

from router.cli.main import _build_eval_summary, _write_eval_report
from router.core.contracts import AnswerResult, TaskEnvelope, TokenUsage


class EvalSummaryTests(unittest.TestCase):
    def test_eval_summary_counts_routes_tokens_and_accuracy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            expected = Path(tmp) / "expected.jsonl"
            expected.write_text(
                '{"id":"1","answer":"4"}\n{"id":"2","answer":"corrected"}\n',
                encoding="utf-8",
            )
            tasks = [
                TaskEnvelope(
                    id="1",
                    input_text="What is 2+2?",
                    metadata={"category": "facil", "difficulty": "easy", "expected_route": "m1_approved"},
                ),
                TaskEnvelope(
                    id="2",
                    input_text="Repair this",
                    metadata={"category": "matematica", "difficulty": "medium", "expected_route": "fireworks_replaced"},
                ),
            ]
            results = [
                AnswerResult(
                    id="1",
                    answer="4",
                    route="m1_approved",
                    remote_tokens=TokenUsage.empty(),
                    metadata={"latency_m1_ms": 10, "latency_m2a_ms": 5},
                ),
                AnswerResult(
                    id="2",
                    answer="corrected",
                    route="fireworks_replaced",
                    remote_tokens=TokenUsage(prompt=3, completion=4, total=7),
                    metadata={"latency_fireworks_ms": 20, "fireworks_parse_failed": False},
                ),
            ]

            summary = _build_eval_summary(tasks, results, expected)

        self.assertEqual(summary["routes"]["m1_approved"], 1)
        self.assertEqual(summary["routes"]["fireworks_replaced"], 1)
        self.assertEqual(summary["remote_tokens"]["total"], 7)
        self.assertEqual(summary["exact_match_rate"], 1.0)
        self.assertEqual(summary["escalation_rate"], 0.5)
        self.assertEqual(summary["replacement_rate"], 0.5)
        self.assertEqual(summary["categories"]["facil"]["tasks"], 1)
        self.assertEqual(summary["categories"]["matematica"]["remote_tokens"]["total"], 7)
        self.assertEqual(summary["expected_route"]["match_rate"], 1.0)

    def test_eval_report_writes_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.md"
            summary = {
                "tasks": 1,
                "exact_match_rate": 1.0,
                "escalation_rate": 0.0,
                "replacement_rate": 0.0,
                "parse_failures": 0,
                "remote_tokens": {"total": 0},
                "routes": {"m1_approved": 1},
                "latency_ms": {"latency_m1_ms": 1},
            }

            _write_eval_report(report, summary)

            content = report.read_text(encoding="utf-8")

        self.assertIn("# Eval Report", content)
        self.assertIn("exact_match_rate", content)


if __name__ == "__main__":
    unittest.main()
