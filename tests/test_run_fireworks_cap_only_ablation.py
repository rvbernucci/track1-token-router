import unittest

from scripts.run_fireworks_cap_only_ablation import cap


class FireworksCapOnlyAblationTests(unittest.TestCase):
    def test_reasoning_and_code_caps_prioritize_accuracy(self):
        self.assertEqual(512, cap({"category": "code_generation"}))
        self.assertEqual(384, cap({"category": "logic_puzzle"}))
        self.assertEqual(192, cap({"category": "math_reasoning"}))
        self.assertEqual(384, cap({"category": "ner"}))


if __name__ == "__main__":
    unittest.main()
