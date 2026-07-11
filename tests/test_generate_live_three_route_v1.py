import unittest
from collections import Counter

from scripts.generate_live_three_route_v1 import generate


class LiveThreeRouteCorpusTests(unittest.TestCase):
    def test_corpus_is_balanced_and_frozen(self):
        rows = generate()
        self.assertEqual(len(rows), 96)
        self.assertEqual(set(Counter(row["category"] for row in rows).values()), {12})
        self.assertEqual(Counter(row["expected_route"] for row in rows), {"fireworks": 72, "deterministic": 12, "e2b": 12})
        self.assertEqual(len({row["prompt_sha256"] for row in rows}), 96)


if __name__ == "__main__":
    unittest.main()
