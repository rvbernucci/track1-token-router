from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.run_codex_fireworks_champion_v3 import merge_atomic, validate_batch


def _batch():
    return [{"blind_id": "x"}, {"blind_id": "y"}]


class CodexFireworksChampionV3Tests(unittest.TestCase):
    def test_validates_complete_consistent_batch(self):
        payload = {"judgments": [
            {"blind_id": "x", "valid_a": True, "valid_b": False, "winner": "a", "reason": "A satisfies the rubric."},
            {"blind_id": "y", "valid_a": True, "valid_b": True, "winner": "tie", "reason": "Both satisfy it."},
        ]}
        self.assertEqual(2, len(validate_batch(_batch(), payload)))

    def test_rejects_missing_or_inconsistent_rows(self):
        with self.assertRaisesRegex(ValueError, "count mismatch"):
            validate_batch(_batch(), {"judgments": []})
        with self.assertRaisesRegex(ValueError, "contradicts"):
            validate_batch([{"blind_id": "x"}], {"judgments": [{"blind_id": "x", "valid_a": False, "valid_b": True, "winner": "a", "reason": "bad"}]})

    def test_atomic_merge_is_resumable_and_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "judgments.jsonl"
            row = {"blind_id": "x", "valid_a": True, "valid_b": False, "winner": "a", "reason": "valid"}
            self.assertEqual(1, merge_atomic(path, [row]))
            self.assertEqual(1, merge_atomic(path, [row]))
            self.assertEqual(row, json.loads(path.read_text()))
            with self.assertRaisesRegex(ValueError, "immutable"):
                merge_atomic(path, [{**row, "winner": "tie"}])


if __name__ == "__main__":
    unittest.main()
