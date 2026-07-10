import json
import tempfile
import unittest
from pathlib import Path

from scripts.merge_engine_judgments import merge_judgments


class MergeEngineJudgmentsTests(unittest.TestCase):
    def test_merges_distinct_candidate_judge_pairs_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = root / "left.jsonl"
            right = root / "right.jsonl"
            output = root / "merged.jsonl"
            left.write_text(json.dumps(_row("candidate-a", "judge-a")) + "\n", encoding="utf-8")
            right.write_text(json.dumps(_row("candidate-a", "judge-b")) + "\n", encoding="utf-8")

            report = merge_judgments([left, right], output)

            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(report["rows"], 2)
        self.assertEqual({row["judge_model"] for row in rows}, {"judge-a", "judge-b"})

    def test_rejects_duplicate_candidate_judge_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = root / "left.jsonl"
            right = root / "right.jsonl"
            output = root / "merged.jsonl"
            row = _row("candidate-a", "judge-a")
            left.write_text(json.dumps(row) + "\n", encoding="utf-8")
            right.write_text(json.dumps(row) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Duplicate judgment key"):
                merge_judgments([left, right], output)

        self.assertFalse(output.exists())


def _row(candidate_id, judge_model):
    return {
        "schema_version": "engine-outcome-judgment-v1",
        "candidate_id": candidate_id,
        "engine": "gemma_e2b",
        "engine_version": "v1",
        "judge_model": judge_model,
        "verdict": "correct",
        "confidence": 0.9,
        "format_valid": True,
        "rationale": "Correct.",
        "provenance": {},
    }


if __name__ == "__main__":
    unittest.main()
