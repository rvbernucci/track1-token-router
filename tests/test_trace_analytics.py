import tempfile
import unittest
from pathlib import Path

from router.analytics.traces import (
    expand_log_paths,
    load_trace_records,
    summarize_traces,
    write_trace_summary_report,
)


class TraceAnalyticsTests(unittest.TestCase):
    def test_fixture_trace_summary_counts_routes_tokens_and_failures(self) -> None:
        paths = expand_log_paths(["fixtures/logs/sample-run.jsonl"])
        records, errors = load_trace_records(paths)
        summary = summarize_traces(records, source_files=paths, ingestion_errors=errors)

        self.assertEqual(errors, [])
        self.assertEqual(summary["records"], 3)
        self.assertEqual(summary["routes"]["m1_approved"], 1)
        self.assertEqual(summary["routes"]["fireworks_replaced"], 1)
        self.assertEqual(summary["remote_tokens"]["total"], 280)
        self.assertEqual(summary["latency_ms"]["latency_fireworks_ms"], 95)
        self.assertEqual(summary["parse_failures"], 1)
        self.assertEqual(summary["errors"], 1)

    def test_empty_trace_summary_is_valid(self) -> None:
        summary = summarize_traces([])

        self.assertTrue(summary["empty_run"])
        self.assertEqual(summary["records"], 0)
        self.assertEqual(summary["routes"], {})

    def test_trace_report_is_written(self) -> None:
        paths = expand_log_paths(["fixtures/logs/sample-run.jsonl"])
        records, errors = load_trace_records(paths)
        summary = summarize_traces(records, source_files=paths, ingestion_errors=errors)
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "trace-summary.md"
            write_trace_summary_report(report, summary)
            content = report.read_text(encoding="utf-8")

        self.assertIn("Trace Summary", content)
        self.assertIn("fireworks_replaced", content)


if __name__ == "__main__":
    unittest.main()
