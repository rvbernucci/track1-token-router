import json
from pathlib import Path
import tempfile
import unittest

from scripts.materialize_answer_contract_candidates import materialize


class MaterializeAnswerContractCandidatesTests(unittest.TestCase):
    def test_materializes_changed_and_unchanged_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "candidates.jsonl"
            rows = [
                {
                    "id": "candidate-1",
                    "task_id": "t1",
                    "task_text": "What is 12 - 5? Return only the number.",
                    "answer": "The answer is 7.",
                },
                {
                    "id": "candidate-2",
                    "task_id": "t2",
                    "task_text": "Explain photosynthesis briefly.",
                    "answer": "Plants convert light into chemical energy.",
                },
            ]
            source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

            result = materialize(source)

        self.assertEqual(result["summary"]["rows"], 2)
        self.assertEqual(result["summary"]["changed"], 1)
        self.assertEqual(result["changed_rows"][0]["answer"], "7")
        self.assertEqual(result["changed_rows"][0]["answer_before_contract"], "The answer is 7.")
        self.assertEqual(result["rows"][1]["answer"], "Plants convert light into chemical energy.")


if __name__ == "__main__":
    unittest.main()
