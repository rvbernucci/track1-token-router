import json
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_answer_contract_candidates import evaluate


class EvaluateAnswerContractCandidatesTests(unittest.TestCase):
    def test_reports_recovery_without_counting_ambiguous_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks.jsonl"
            candidates = root / "candidates.jsonl"
            tasks.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "id": "label",
                                "input_text": "Classify sentiment. Answer exactly one label: positive, negative, or neutral.",
                                "evaluation": {"type": "label", "expected": "positive"},
                            }
                        ),
                        json.dumps(
                            {
                                "id": "number",
                                "input_text": "Provide only the final numeric value.",
                                "evaluation": {"type": "exact", "expected": "7"},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            candidates.write_text(
                "\n".join(
                    [
                        json.dumps({"task_id": "label", "answer": "The sentiment is positive."}),
                        json.dumps({"task_id": "number", "answer": "12 minus 5 equals 7."}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            report = evaluate(tasks, candidates)

        self.assertEqual(report["summary"]["recovered"], 1)
        self.assertEqual(report["summary"]["regressed"], 0)
        self.assertEqual(report["summary"]["final_correct"], 1)


if __name__ == "__main__":
    unittest.main()
