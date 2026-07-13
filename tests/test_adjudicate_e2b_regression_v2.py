import unittest

from scripts.adjudicate_e2b_regression_v2 import _disagreement_queue, _label, _mechanical


class AdjudicateE2BV2Tests(unittest.TestCase):
    def test_numeric_and_label_mechanical_proof(self) -> None:
        number = {"reference_answer": "1250", "output_shape": "number"}
        label = {"reference_answer": "positive", "output_shape": "label"}
        self.assertEqual(_mechanical(number, "1,250", True, "math_reasoning")["verdict"], "correct")
        self.assertEqual(_mechanical(label, "negative", True, "sentiment")["verdict"], "incorrect")

    def test_invalid_reference_shape_requires_semantic_judgment(self) -> None:
        number = {"reference_answer": "{3}", "output_shape": "number"}
        json_reference = {"reference_answer": "Dana", "output_shape": "json"}

        numeric_result = _mechanical(number, "3", True, "math_reasoning")
        json_result = _mechanical(json_reference, '{"answer":"Dana"}', True, "logic_puzzle")

        self.assertFalse(numeric_result["hard"])
        self.assertEqual(numeric_result["reason"], "invalid_numeric_reference")
        self.assertFalse(json_result["hard"])
        self.assertEqual(json_result["reason"], "invalid_json_reference")

    def test_semantic_mismatch_abstains(self) -> None:
        reference = {"reference_answer": "Paris", "output_shape": "short_text"}
        result = _mechanical(reference, "The capital is Paris.", True, "factual_qa")
        self.assertEqual(result["verdict"], "uncertain")
        self.assertFalse(result["hard"])

    def test_invalid_contract_is_hard_incorrect(self) -> None:
        reference = {"reference_answer": "{}", "output_shape": "json"}
        self.assertEqual(_mechanical(reference, "bad", False, "ner")["verdict"], "incorrect")

    def test_registered_hard_gate_can_prove_correctness(self) -> None:
        reference = {"reference_answer": "different surface form", "output_shape": "short_text"}
        evidence = {"hard_gate_passed": True, "verifier_family": "proof_math"}
        result = _mechanical(reference, "42", True, "math_reasoning", local_evidence=evidence)
        self.assertEqual(result, {"verdict": "correct", "hard": True, "reason": "verified:proof_math"})

    def test_mechanical_precedes_judges_and_disagreement_stays_uncertain(self) -> None:
        base = {
            "task_id": "t1", "split": "train", "category": "factual_qa",
            "answer_contract": {"valid": True}, "normalization_changed": False,
            "contract_idempotent": True, "assessment_valid": True,
            "functiongemma_assessment": {}, "answer": "x",
        }
        mechanical = {**base, "mechanical": {"hard": True, "verdict": "incorrect"}}
        self.assertEqual(_label(mechanical, [{"verdict": "correct", "judge_model": "a"}, {"verdict": "correct", "judge_model": "b"}])["final_label"], "incorrect")
        semantic = {**base, "mechanical": {"hard": False, "verdict": "uncertain"}}
        result = _label(semantic, [{"verdict": "correct", "judge_model": "a"}, {"verdict": "incorrect", "judge_model": "b"}])
        self.assertEqual(result["final_label"], "uncertain")

        adjudicated = _label(
            semantic,
            [
                {"verdict": "correct", "judge_model": "a"},
                {"verdict": "incorrect", "judge_model": "b"},
                {"verdict": "correct", "judge_model": "c"},
            ],
        )
        self.assertEqual(adjudicated["final_label"], "correct")
        self.assertEqual(adjudicated["evidence_source"], "judge_adjudication")

    def test_only_pair_disagreements_enter_third_judge_queue(self) -> None:
        candidate = {"id": "c1", "mechanical": {"hard": False}}
        judgments = {
            "c1": [
                {"verdict": "correct", "judge_model": "a"},
                {"verdict": "incorrect", "judge_model": "b"},
            ]
        }
        self.assertEqual(_disagreement_queue([candidate], judgments), [candidate])


if __name__ == "__main__":
    unittest.main()
