import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from router.core.contracts import AssessmentScores, Intent, TaskAssessment, TaskEnvelope
from router.orchestration.e2b_extra_trees_gate import E2BExtraTreesGate


POLICY = Path("configs/e2b-extra-trees-code-debug-v1.json")
POLICY_SHA256 = "d6c8d222f62d545b299d4ee4506f3a782c4c998e054781ca3aeb0fe5e120df20"
PROTECTED_COHORT = {
    "e2b_v2_code_debugging_1470",
    "e2b_v2_code_debugging_1471",
    "e2b_v2_code_debugging_1493",
    "s70_code_debugging_easy_081",
    "s70_code_debugging_easy_083",
    "s70_code_debugging_easy_084",
    "s70_code_debugging_easy_086",
    "s70_code_debugging_easy_087",
    "s70_code_debugging_easy_090",
    "s70_code_debugging_easy_092",
    "s70_code_debugging_easy_093",
    "s70_code_debugging_easy_094",
    "s70_code_debugging_easy_096",
}


def _rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class E2BExtraTreesGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = E2BExtraTreesGate.load(POLICY, expected_sha256=POLICY_SHA256)

    def test_policy_is_hash_pinned_and_code_debugging_only(self) -> None:
        self.assertEqual(hashlib.sha256(POLICY.read_bytes()).hexdigest(), POLICY_SHA256)
        self.assertTrue(self.gate.should_probe(Intent.CODE_DEBUGGING))
        self.assertTrue(self.gate.should_probe("code_debugging"))
        self.assertFalse(self.gate.should_probe(Intent.CODE_GENERATION))
        self.assertFalse(self.gate.should_probe("sentiment"))

    def test_missing_or_wrong_hash_pin_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            E2BExtraTreesGate.load(POLICY, expected_sha256="")
        with self.assertRaises(ValueError):
            E2BExtraTreesGate.load(POLICY, expected_sha256="0" * 64)

    def test_non_code_intent_and_invalid_assessment_fail_closed(self) -> None:
        task = TaskEnvelope("Return only the corrected Python function.", "t1")
        sentiment = TaskAssessment(Intent.SENTIMENT, AssessmentScores(5, 2, 1, 2, 2))
        self.assertFalse(self.gate.evaluate(task, sentiment, "positive").accepted)
        malformed = {"intent": "code_debugging", "scores": {"deterministic_fit": 5}}
        decision = self.gate.evaluate(task, malformed, "def fixed():\n    return True")
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "extra_trees_feature_failure")

    def test_answer_contract_failure_cannot_be_released(self) -> None:
        task = TaskEnvelope(
            "Fix this Python bug and return only the corrected function.\n```python\ndef f(): return 1 / 0\n```",
            "t1",
        )
        assessment = TaskAssessment(Intent.CODE_DEBUGGING, AssessmentScores(5, 5, 1, 5, 3))
        decision = self.gate.evaluate(task, assessment, "")
        self.assertFalse(decision.accepted)
        self.assertFalse(decision.contract_valid)
        self.assertTrue(decision.reason.startswith("answer_contract_rejected:"))

    def test_malformed_tree_artifact_is_rejected_even_with_valid_pin(self) -> None:
        payload = json.loads(POLICY.read_text(encoding="utf-8"))
        payload["trees"] = [{"p": 0.5, "f": len(payload["feature_names"]), "t": 0, "l": {"p": 0.1}, "r": {"p": 0.9}}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):
                E2BExtraTreesGate.load(path, expected_sha256=digest)

    def test_protected_code_debugging_cohort_replays_13_of_13(self) -> None:
        required = (
            Path("evals/e2b-expansion-v1/sealed/tasks/final_holdout.jsonl"),
            Path("evals/e2b-regression-v2/inputs/final_holdout.jsonl"),
            Path("evals/e2b-expansion-v1/adjudication/sealed/candidates.jsonl"),
            Path("evals/e2b-regression-v2-adjudication/sealed/final-holdout-candidates.jsonl"),
            Path("evals/e2b-expansion-v1/adjudication/sealed/labels.jsonl"),
            Path("evals/e2b-regression-v2-adjudication/sealed/final-holdout-labels.jsonl"),
        )
        if not all(path.is_file() for path in required):
            self.skipTest("protected E2B replay corpora are not included in the public checkout")
        prompts = {}
        for path in required[:2]:
            prompts.update({row["task_id"]: row["prompt"] for row in _rows(path)})
        candidates = {}
        for path in required[2:4]:
            candidates.update({row["task_id"]: row for row in _rows(path)})
        labels = {}
        for path in required[4:]:
            labels.update({row["task_id"]: int(row["binary_label"]) for row in _rows(path)})

        selected = set()
        for task_id, candidate in candidates.items():
            answer = candidate.get("raw_answer") or candidate["answer"]
            decision = self.gate.evaluate(
                TaskEnvelope(prompts[task_id], task_id),
                candidate["functiongemma_assessment"],
                answer,
            )
            if decision.accepted:
                selected.add(task_id)

        self.assertEqual(selected, PROTECTED_COHORT)
        self.assertEqual(sum(labels[task_id] for task_id in selected), 13)


if __name__ == "__main__":
    unittest.main()
