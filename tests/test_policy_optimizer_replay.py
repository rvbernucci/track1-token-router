import tempfile
import unittest
from pathlib import Path

from router.adapters.io import load_jsonl_tasks
from scripts.optimize_policy import run_policy_optimization, write_policy_pareto_report
from scripts.replay_decision import replay_decision, write_replay_report


class PolicyOptimizerTests(unittest.TestCase):
    def test_optimizer_returns_recommended_non_dominated_profile(self) -> None:
        tasks = load_jsonl_tasks(Path("evals/offline/tasks.jsonl"))

        report = run_policy_optimization(tasks=tasks, expected_path=Path("evals/offline/expected.jsonl"))

        self.assertTrue(report["recommended"])
        self.assertFalse(report["recommended"]["dominated"])
        self.assertGreaterEqual(report["candidates"], 1)
        self.assertGreaterEqual(report["dominated"], 1)
        self.assertGreaterEqual(report["recommended"]["exact_match_rate"], 0.9)

    def test_optimizer_writes_pareto_report(self) -> None:
        tasks = load_jsonl_tasks(Path("evals/offline/tasks.jsonl"))
        report = run_policy_optimization(tasks=tasks, expected_path=Path("evals/offline/expected.jsonl"))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "policy-pareto.md"
            write_policy_pareto_report(out, report)
            content = out.read_text(encoding="utf-8")

        self.assertIn("Policy Pareto Report", content)
        self.assertIn("recommended_profile", content)
        self.assertIn("dominated", content)


class DecisionReplayTests(unittest.TestCase):
    def test_replay_shows_solver_path_for_arithmetic(self) -> None:
        replay = replay_decision("What is 6 * 7? Return only the number.")

        self.assertEqual(replay["route"], "solver_arithmetic")
        self.assertEqual(replay["answer"], "42")
        self.assertEqual(replay["decision"]["policy_decision"]["action"], "approve")
        self.assertFalse(replay["decision"]["remote_would_call"])

    def test_replay_writes_markdown_with_decision_sections(self) -> None:
        replay = replay_decision("Who is the CEO of AMD today?")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "decision-replay.md"
            write_replay_report(out, replay)
            content = out.read_text(encoding="utf-8")

        self.assertIn("Decision Replay", content)
        self.assertIn("Risk Signals", content)
        self.assertIn("Budget Decision", content)
        self.assertIn("Policy Decision", content)
        self.assertIn("Final Validator", content)


if __name__ == "__main__":
    unittest.main()
