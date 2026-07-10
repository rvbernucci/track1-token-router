import json
import tempfile
import unittest
from pathlib import Path

from scripts.transfer_equivalent_judgments import transfer


class TransferEquivalentJudgmentsTests(unittest.TestCase):
    def test_transfers_only_exact_answer_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.jsonl"
            target = root / "target.jsonl"
            judgments = root / "judgments.jsonl"
            output = root / "output.jsonl"
            common = {
                "task_id": "task",
                "model_id": "model",
                "generation_limit_tokens": 96,
                "answer": "exact",
                "failure": False,
                "refusal": False,
            }
            source.write_text(json.dumps({**common, "id": "source", "runtime_id": "gpu"}) + "\n")
            target.write_text(json.dumps({**common, "id": "target", "runtime_id": "cpu"}) + "\n")
            judgments.write_text(json.dumps({"candidate_id": "source", "judge_model": "judge", "verdict": "correct"}) + "\n")

            result = transfer(
                source_candidates=source,
                target_candidates=target,
                source_judgments=judgments,
                output=output,
            )
            row = json.loads(output.read_text())

        self.assertEqual(result["judgments_transferred"], 1)
        self.assertEqual(row["candidate_id"], "target")
        self.assertEqual(row["source_candidate_id"], "source")
        self.assertEqual(row["transfer"]["target_runtime_id"], "cpu")

    def test_rejects_changed_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.jsonl"
            target = root / "target.jsonl"
            judgments = root / "judgments.jsonl"
            common = {"task_id": "task", "model_id": "model", "generation_limit_tokens": 96, "failure": False}
            source.write_text(json.dumps({**common, "id": "source", "answer": "one"}) + "\n")
            target.write_text(json.dumps({**common, "id": "target", "answer": "two"}) + "\n")
            judgments.write_text("")
            with self.assertRaises(ValueError):
                transfer(
                    source_candidates=source,
                    target_candidates=target,
                    source_judgments=judgments,
                    output=root / "output.jsonl",
                )


if __name__ == "__main__":
    unittest.main()
