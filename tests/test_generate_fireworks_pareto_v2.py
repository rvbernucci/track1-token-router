import unittest
from collections import Counter

from scripts.generate_fireworks_pareto_v2 import generate


class FireworksParetoV2CorpusTests(unittest.TestCase):
    def test_balanced_mechanical_corpus(self):
        rows = generate()
        self.assertEqual(len(rows), 192)
        self.assertEqual(set(Counter(row["category"] for row in rows).values()), {24})
        self.assertEqual(Counter(row["difficulty"] for row in rows), {"easy": 64, "medium": 64, "hard": 64})
        self.assertEqual(Counter(row["split"] for row in rows), {"development": 160, "sealed": 32})
        self.assertEqual(len({row["prompt_sha256"] for row in rows}), 192)


if __name__ == "__main__":
    unittest.main()
