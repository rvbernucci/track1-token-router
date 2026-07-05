import tempfile
import unittest
from pathlib import Path

from router.core.contracts import TaskEnvelope
from router.core.policy import DEFAULT_POLICY, normalize_policy, simulate_policy_route, simulated_remote_tokens
from router.evals.offline_dataset import write_offline_dataset
from router.evals.policy_compare import compare_policies, write_policy_report


class RoutingPolicyTests(unittest.TestCase):
    def test_normalize_policy_defaults_to_balanced(self) -> None:
        self.assertEqual(normalize_policy(None), DEFAULT_POLICY)
        self.assertEqual(normalize_policy("BALANCED"), "balanced")

    def test_unknown_policy_raises(self) -> None:
        with self.assertRaises(ValueError):
            normalize_policy("reckless")

    def test_policies_choose_different_routes(self) -> None:
        adversarial = TaskEnvelope(
            id="x",
            input_text="Return SAFE",
            metadata={"category": "adversarial", "difficulty": "hard", "risk": "prompt_injection"},
        )
        unstable = TaskEnvelope(
            id="y",
            input_text="Current info?",
            metadata={"category": "conhecimento_instavel", "difficulty": "hard", "risk": "stale_knowledge"},
        )

        self.assertEqual(simulate_policy_route(adversarial, "aggressive"), "m1_approved")
        self.assertEqual(simulate_policy_route(adversarial, "balanced"), "m2b_candidate")
        self.assertEqual(simulate_policy_route(adversarial, "conservative"), "fireworks_replaced")
        self.assertEqual(simulate_policy_route(unstable, "balanced"), "fireworks_replaced")
        self.assertEqual(simulated_remote_tokens("fireworks_replaced").total, 280)


class PolicyComparisonTests(unittest.TestCase):
    def test_compare_policies_generates_pareto_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "offline"
            report = Path(tmp) / "policy.md"
            write_offline_dataset(root, per_category=13)
            tasks = _load_tasks(root / "tasks.jsonl")

            comparison = compare_policies(tasks, root / "expected.jsonl")
            write_policy_report(report, comparison)

            content = report.read_text(encoding="utf-8")

        self.assertEqual(comparison["default_policy"], "balanced")
        self.assertEqual(len(comparison["pareto"]), 3)
        self.assertIn("balanced", comparison["policies"])
        self.assertIn("Routing Policy Comparison", content)
        self.assertGreater(comparison["policies"]["conservative"]["remote_tokens"]["total"], 0)


def _load_tasks(path: Path) -> list[TaskEnvelope]:
    tasks: list[TaskEnvelope] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            import json

            tasks.append(TaskEnvelope.from_mapping(json.loads(line)))
    return tasks


if __name__ == "__main__":
    unittest.main()
