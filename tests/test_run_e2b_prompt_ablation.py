import unittest

from scripts.run_e2b_prompt_ablation import INTENT, balanced_sample, messages


class E2BPromptAblationTests(unittest.TestCase):
    def test_raw_protocol_preserves_prompt(self):
        self.assertEqual([{"role": "user", "content": "hello"}], messages("hello", "factual_qa", "raw"))

    def test_contract_does_not_modify_user_prompt(self):
        packet = messages("hello", "factual_qa", "intent_contract")
        self.assertEqual("hello", packet[-1]["content"])
        self.assertIn("factually correct", packet[0]["content"])

    def test_balanced_sample_is_exact(self):
        tasks = []
        metadata = {}
        for category in INTENT:
            for index in range(3):
                task_id = f"{category}-{index}"
                tasks.append({"task_id": task_id, "prompt": task_id})
                metadata[task_id] = {"category": category}
        selected = balanced_sample(tasks, metadata, 2)
        self.assertEqual(16, len(selected))


if __name__ == "__main__":
    unittest.main()
