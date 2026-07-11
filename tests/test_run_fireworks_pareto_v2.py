import unittest

from scripts.run_fireworks_pareto_v2 import _bootstrap_lineage_ci, _bootstrap_mean_ci, _select_policy


class FireworksParetoV2Tests(unittest.TestCase):
    def test_bootstrap_interval_is_deterministic(self):
        self.assertEqual(_bootstrap_mean_ci([1, 2, 3], 100), _bootstrap_mean_ci([1, 2, 3], 100))

    def test_policy_prefers_accuracy_before_tokens(self):
        rows = []
        for model, valid, tokens in (("a", True, 50), ("b", False, 1)):
            rows.append({"split":"development","category":"math_reasoning","model":model,"valid":valid,"usage":{"total":tokens}})
        self.assertEqual(_select_policy(rows, ("a", "b"))["intent_models"]["math_reasoning"], "a")

    def test_lineage_bootstrap_groups_mutations(self):
        interval = _bootstrap_lineage_ci([1, 1, 3, 3], ["a", "a", "b", "b"], 100)
        self.assertEqual(interval, [1, 3])


if __name__ == "__main__":
    unittest.main()
