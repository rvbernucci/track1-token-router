import unittest

from router.core.contracts import TokenUsage
from router.orchestration.budget import (
    BudgetManager,
    TaskBudget,
    estimate_remote_tokens_for_route,
    summarize_policy_budget,
)


class BudgetManagerTests(unittest.TestCase):
    def test_allows_remote_when_estimate_is_inside_budget(self) -> None:
        manager = BudgetManager(TaskBudget(max_remote_tokens_per_task=300, max_remote_tokens_per_run=600))

        decision = manager.allow_remote(estimated_remote_tokens=280, latency_risk_ms=100)

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision, "allow_remote")

    def test_denies_remote_when_task_token_budget_is_exceeded(self) -> None:
        manager = BudgetManager(TaskBudget(max_remote_tokens_per_task=100, max_remote_tokens_per_run=600))

        decision = manager.allow_remote(estimated_remote_tokens=280)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.decision, "deny_remote_budget_exceeded")
        self.assertEqual(decision.reason, "estimated_remote_tokens_exceed_task_budget")

    def test_denies_remote_when_latency_budget_is_exceeded(self) -> None:
        manager = BudgetManager(TaskBudget(max_remote_latency_ms=50))

        decision = manager.allow_remote(estimated_remote_tokens=10, latency_risk_ms=90)

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.decision, "deny_remote_latency_risk")

    def test_records_actual_usage_and_parse_failure_penalty(self) -> None:
        manager = BudgetManager(TaskBudget(max_remote_tokens_per_run=600, parse_failure_penalty_tokens=200))

        manager.record_actual(TokenUsage(prompt=240, completion=40, total=280), latency_ms=120, parse_failed=True)

        snapshot = manager.snapshot()
        self.assertEqual(snapshot["remote_tokens_spent"], 480)
        self.assertEqual(snapshot["remote_tokens_remaining"], 120)
        self.assertEqual(snapshot["parse_failures"], 1)

    def test_policy_budget_summary_flags_run_budget_violation(self) -> None:
        summary = {
            "remote_tokens": {"total": 700},
            "latency_ms": {"latency_fireworks_ms": 10},
            "parse_failures": 0,
        }

        budget = summarize_policy_budget(summary, TaskBudget(max_remote_tokens_per_run=600))

        self.assertEqual(budget["run_budget_violations"], 1)
        self.assertEqual(budget["budget_violations"], 1)

    def test_remote_route_estimator(self) -> None:
        self.assertEqual(estimate_remote_tokens_for_route("fireworks_replaced"), 280)
        self.assertEqual(estimate_remote_tokens_for_route("m1_approved"), 0)


if __name__ == "__main__":
    unittest.main()
