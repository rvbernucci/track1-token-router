import json
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_e2b_token_ladder import analyze


class AnalyzeE2BTokenLadderTests(unittest.TestCase):
    def test_separates_real_recovery_from_judge_flip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stages = []
            answers = {
                96: {"a": "partial", "b": "same", "c": "wrong"},
                192: {"a": "partial complete", "b": "same", "c": "wrong longer"},
            }
            outcomes = {
                96: {"a": "incorrect", "b": "incorrect", "c": "incorrect"},
                192: {"a": "correct", "b": "correct", "c": "incorrect"},
            }
            for limit in (96, 192):
                candidates = root / f"candidates-{limit}.jsonl"
                consensus = root / f"consensus-{limit}.jsonl"
                candidate_rows = []
                consensus_rows = []
                for task_id in ("a", "b", "c"):
                    candidate_rows.append({"task_id": task_id, "answer": answers[limit][task_id]})
                    consensus_rows.append(
                        {
                            "task_id": task_id,
                            "outcome": outcomes[limit][task_id],
                            "intent": "factual_qa",
                            "scores": {
                                "deterministic_fit": 1,
                                "format_complexity": 2,
                                "generation_demand": 3,
                                "knowledge_uncertainty": 4,
                                "reasoning_demand": 5,
                            },
                            "latency_ms": float(limit),
                        }
                    )
                candidates.write_text("".join(json.dumps(row) + "\n" for row in candidate_rows))
                consensus.write_text("".join(json.dumps(row) + "\n" for row in consensus_rows))
                stages.append((limit, candidates, consensus))

            report = analyze(stages)

        transition = report["transitions"][0]
        self.assertEqual(transition["genuine_recoveries"], 1)
        self.assertEqual(transition["judge_flips_without_output_change"], 1)
        self.assertEqual(transition["classifications"]["still_failed"], 1)
        self.assertEqual(report["summary"]["genuine_incremental_recoveries"], 1)


if __name__ == "__main__":
    unittest.main()
