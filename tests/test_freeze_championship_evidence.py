from __future__ import annotations

from pathlib import Path
import unittest

from scripts.freeze_championship_evidence import verify


class FreezeChampionshipEvidenceTests(unittest.TestCase):
    def test_checked_in_evidence_pack_is_complete_and_hash_pinned(self) -> None:
        self.assertEqual(verify(Path("data/championship-ablation")), [])


if __name__ == "__main__":
    unittest.main()
