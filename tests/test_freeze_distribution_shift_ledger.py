import json
import unittest
from pathlib import Path


class DistributionLedgerTests(unittest.TestCase):
    def test_frozen_ledger_is_paired_and_complete(self):
        path=Path("evals/distribution-shift-v1/ledger.jsonl")
        if not path.exists(): self.skipTest("ledger not frozen yet")
        rows=[json.loads(line) for line in path.read_text().splitlines() if line]
        self.assertEqual(len(rows),96)
        self.assertEqual(len({row["task_id"] for row in rows}),96)
        self.assertTrue(all(row["current_total_tokens"]<=row["baseline_total_tokens"] for row in rows))


if __name__=="__main__":unittest.main()
