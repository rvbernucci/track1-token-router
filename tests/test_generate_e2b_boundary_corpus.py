import unittest
from collections import Counter

from scripts.generate_e2b_boundary_corpus import generate


class E2BBoundaryCorpusTests(unittest.TestCase):
    def test_generates_balanced_unique_mechanical_corpus(self):
        rows = generate(60, 65065)
        self.assertEqual(len(rows), 480)
        self.assertEqual(set(Counter(row["category"] for row in rows).values()), {60})
        self.assertEqual(len({row["prompt_sha256"] for row in rows}), 480)
        self.assertTrue(all(row["evaluation"]["expected"] is not None for row in rows))


if __name__ == "__main__":
    unittest.main()
