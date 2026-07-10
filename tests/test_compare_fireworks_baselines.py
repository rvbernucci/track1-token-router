import unittest
import json
from pathlib import Path

from scripts.compare_fireworks_baselines import _summarize, _wilson_lower, render_markdown


class CompareFireworksBaselinesTests(unittest.TestCase):
    def test_baseline_judge_policy_never_uses_self_judging(self):
        root = Path(__file__).resolve().parents[1]
        policy = json.loads(
            (root / "configs" / "fireworks-baseline-judge-policy.json").read_text(encoding="utf-8")
        )

        for candidate_model, judge_models in policy.items():
            self.assertEqual(len(judge_models), 2)
            self.assertNotIn(candidate_model, judge_models)

    def test_conservative_accuracy_counts_disagreement_as_failure(self):
        metrics = _summarize([
            {"correct": True, "tokens": 10},
            {"correct": False, "tokens": 20},
            {"correct": None, "tokens": 30},
        ])
        self.assertEqual(metrics["conservative_accuracy"], 1 / 3)
        self.assertEqual(metrics["binary_accuracy"], 0.5)
        self.assertEqual(metrics["average_tokens"], 20)
        self.assertLess(metrics["conservative_wilson_lower_95"], metrics["conservative_accuracy"])

    def test_wilson_lower_is_zero_without_observations(self):
        self.assertEqual(_wilson_lower(0, 0), 0.0)

    def test_markdown_exposes_locked_metrics(self):
        report = {
            "model_summary": {"model": {"test": _summarize([{"correct": True, "tokens": 10}])}},
            "validation_selected_model_by_intent": {"sentiment": "model"},
            "locked_test_policy": _summarize([{"correct": True, "tokens": 10}]),
        }
        rendered = render_markdown(report)
        self.assertIn("Validation-Selected Policy", rendered)
        self.assertIn("Locked-test Fireworks tokens: `10`", rendered)


if __name__ == "__main__":
    unittest.main()
