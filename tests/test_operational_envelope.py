import unittest
from pathlib import Path

from router.adapters.io import load_jsonl_tasks
from router.evals.operational_envelope import (
    LatencyThresholds,
    TokenEnvelopeThresholds,
    build_token_envelope,
    summarize_latency_envelope,
)


class OperationalEnvelopeTests(unittest.TestCase):
    def test_latency_summary_computes_percentiles_and_timeout_probes(self) -> None:
        report = summarize_latency_envelope(
            [10.0, 20.0, 30.0, 40.0],
            batch_elapsed_ms=100.0,
            batch_tasks=4,
            thresholds=LatencyThresholds(
                max_p95_ms=50.0,
                max_batch_ms=200.0,
                min_batch_tasks_per_second=1.0,
                local_timeout_ms=25.0,
                remote_timeout_ms=25.0,
            ),
        )

        self.assertTrue(report["ready"])
        self.assertEqual(report["p50_ms"], 20.0)
        self.assertEqual(report["p95_ms"], 40.0)
        self.assertTrue(report["local_timeout_probe"]["timeout_detected"])
        self.assertTrue(report["remote_timeout_probe"]["timeout_detected"])

    def test_latency_summary_fails_when_p95_exceeds_threshold(self) -> None:
        report = summarize_latency_envelope(
            [10.0, 20.0, 300.0],
            batch_elapsed_ms=100.0,
            batch_tasks=3,
            thresholds=LatencyThresholds(max_p95_ms=100.0),
        )

        self.assertFalse(report["ready"])

    def test_token_envelope_marks_balanced_policy_ready(self) -> None:
        tasks = load_jsonl_tasks(Path("evals/offline/tasks.jsonl"))

        report = build_token_envelope(tasks, thresholds=TokenEnvelopeThresholds())

        self.assertTrue(report["ready"])
        self.assertEqual(report["candidate_policy"], "balanced")
        self.assertGreater(report["candidate"]["run_exposure"], 0)
        self.assertGreaterEqual(len(report["top_tasks"]), 1)
        self.assertIn("fireworks_replaced", report["route_worst_case"])

    def test_token_envelope_can_fail_with_strict_threshold(self) -> None:
        tasks = load_jsonl_tasks(Path("evals/offline/tasks.jsonl"))

        report = build_token_envelope(
            tasks,
            thresholds=TokenEnvelopeThresholds(max_candidate_run_exposure=1, max_candidate_task_exposure=1),
        )

        self.assertFalse(report["ready"])


if __name__ == "__main__":
    unittest.main()
