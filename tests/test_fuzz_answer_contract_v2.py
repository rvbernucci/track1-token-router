import unittest

from scripts.fuzz_answer_contract_v2 import _case_hash, generate


class AnswerContractFuzzV2Tests(unittest.TestCase):
    def test_generation_is_reproducible_and_balanced(self):
        first = generate(2000, 68068)
        second = generate(2000, 68068)
        self.assertEqual(_case_hash(first), _case_hash(second))
        self.assertEqual(len(first), 2000)
        self.assertEqual(len({row["case_id"] for row in first}), 2000)


if __name__ == "__main__":
    unittest.main()
