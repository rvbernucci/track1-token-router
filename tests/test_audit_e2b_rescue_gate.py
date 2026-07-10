import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_e2b_rescue_gate import audit_rescue_gate


class AuditE2BRescueGateTests(unittest.TestCase):
    def test_reports_saved_errors_and_false_rescues_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = root / "tasks.jsonl"
            candidates = root / "candidates.jsonl"
            judgments = root / "judgments.jsonl"
            policy = root / "policy.json"
            tasks.write_text(
                _lines([
                    {"id": "one", "input_text": "Explain one."},
                    {"id": "two", "prompt": "Explain two."},
                    {"id": "three", "messages": [{"role": "user", "content": "Explain three."}]},
                ]),
                encoding="utf-8",
            )
            candidates.write_text(
                _lines([
                    _candidate("c1", "one", "A complete and correct response."),
                    _candidate("c2", "two", "bad loop bad loop bad loop bad loop bad loop bad loop bad loop bad loop"),
                    _candidate("c3", "three", "```text\nA correct answer with an unclosed fence"),
                ]),
                encoding="utf-8",
            )
            judgments.write_text(
                _lines(
                    _judgments("c1", "correct")
                    + _judgments("c2", "incorrect")
                    + _judgments("c3", "correct")
                ),
                encoding="utf-8",
            )
            policy.write_text(json.dumps({"gemma4-e2b": ["judge-a", "judge-b"]}), encoding="utf-8")

            result = audit_rescue_gate(
                tasks_path=tasks,
                candidates_path=candidates,
                judgments_path=judgments,
                judge_policy_path=policy,
            )

            self.assertEqual(result["summary"]["release_correct"], 1)
            self.assertEqual(result["summary"]["rescue_correct"], 1)
            self.assertEqual(result["summary"]["false_rescue"], 1)
            self.assertEqual(result["mechanical_rejection_reasons"]["degenerate_repetition"], 1)
            self.assertEqual(result["mechanical_rejection_reasons"]["unclosed_markdown_fence"], 1)


def _candidate(candidate_id, task_id, answer):
    return {
        "id": candidate_id,
        "task_id": task_id,
        "engine": "gemma_e2b",
        "model_id": "gemma4-e2b",
        "answer": answer,
        "functiongemma_assessment": {"intent": "factual_qa"},
    }


def _judgments(candidate_id, verdict):
    return [
        {"candidate_id": candidate_id, "judge_model": model, "verdict": verdict, "format_valid": True}
        for model in ("judge-a", "judge-b")
    ]


def _lines(rows):
    return "".join(json.dumps(row) + "\n" for row in rows)


if __name__ == "__main__":
    unittest.main()
