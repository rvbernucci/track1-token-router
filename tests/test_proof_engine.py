import json
import hashlib
from pathlib import Path
from decimal import Decimal
import unittest

from router.core.contracts import TaskEnvelope
from router.orchestration.proof_engine import (
    PROOF_SCHEMA_VERSION,
    ProofEnvelope,
    ProofType,
    attempt_proof,
    evaluate_decimal_expression,
    solve_with_proof,
    verify_candidate_against_proof,
)


class ProofEngineTests(unittest.TestCase):
    def test_proof_envelope_round_trips_deterministically(self) -> None:
        solved = solve_with_proof(TaskEnvelope(input_text="What is 15% of 240? Return only the number."))
        self.assertIsNotNone(solved)

        payload = json.loads(solved.proof.to_json())
        restored = ProofEnvelope.from_mapping(payload)

        self.assertEqual(restored, solved.proof)
        self.assertEqual(payload["schema_version"], PROOF_SCHEMA_VERSION)
        self.assertEqual(restored.proof_type, ProofType.PERCENTAGE)

    def test_safe_decimal_ast_supports_bounded_exact_operations(self) -> None:
        result = evaluate_decimal_expression("(12 + 8) * 3 - 5")

        self.assertEqual(str(result.value), "55")
        self.assertTrue(result.exact)
        self.assertIn("multiply:20,3->60", result.trace)

    def test_safe_decimal_ast_rejects_execution_and_unbounded_operations(self) -> None:
        rejected = [
            "__import__('os').system('echo unsafe')",
            "[1, 2, 3]",
            "2 ** 100",
            "1 / 0",
            "1 / 3",
        ]
        for expression in rejected:
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                evaluate_decimal_expression(expression)

        rounded = evaluate_decimal_expression("1 / 3", decimal_places=2)
        self.assertEqual(str(rounded.value), "0.33")

    def test_numeric_mutations_are_canonical_or_safely_rejected(self) -> None:
        accepted = {
            "+1.25e2": "125",
            "-5 + 2": "-3",
            "(.5 + .25) * 4": "3",
        }
        for expression, expected in accepted.items():
            with self.subTest(expression=expression):
                value = evaluate_decimal_expression(expression).value
                self.assertEqual(value, Decimal(expected))
        for expression in ("1,000 + 2", "1,5 + 2", "NaN + 1", "1_000 + 2"):
            with self.subTest(rejected=expression), self.assertRaises(ValueError):
                evaluate_decimal_expression(expression)

    def test_solves_math_families_with_recomputable_proofs(self) -> None:
        cases = {
            "What is 15% of 240? Return only the number.": ("36", ProofType.PERCENTAGE),
            "A value starts at 200 and increases by 10%. What is the final value? Return only the number.": (
                "220",
                ProofType.PERCENTAGE,
            ),
            "If 4 machines produce 20 widgets, how many widgets do 6 machines produce? Return only the number.": (
                "30",
                ProofType.PROPORTIONAL_RATE,
            ),
            "Convert 2.5 kilometers to meters. Return only the number.": ("2500", ProofType.UNIT_CONVERSION),
            "Calculate (12 + 8) * 3. Return only the number.": ("60", ProofType.DECIMAL_AST),
            "Revenue starts at 100 and grows 10% annually for 2 years. What is the projected value?": (
                "121",
                ProofType.COMPOUND_PROJECTION,
            ),
        }
        for prompt, (answer, proof_type) in cases.items():
            with self.subTest(prompt=prompt):
                solved = solve_with_proof(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(solved)
                self.assertEqual(solved.answer, answer)
                self.assertEqual(solved.proof.proof_type, proof_type)
                self.assertTrue(solved.proof.verified)
                self.assertTrue(solved.proof.unique)

    def test_rejects_unit_mismatch_unused_numbers_and_missing_rounding(self) -> None:
        blocked = [
            "Convert 2 meters to kilograms. Return only the number.",
            "What is 15% of 240 if unrelated code 99 is present? Return only the number.",
        ]
        for prompt in blocked:
            with self.subTest(prompt=prompt):
                self.assertIsNone(solve_with_proof(TaskEnvelope(input_text=prompt)))

        rounded = solve_with_proof(
            TaskEnvelope(
                input_text=(
                    "Revenue starts at 100 and grows 7% annually for 3 years. "
                    "What is the projected value? Round to 2 decimal places."
                )
            )
        )
        self.assertIsNotNone(rounded)
        self.assertEqual(rounded.answer, "122.50")
        exact = solve_with_proof(
            TaskEnvelope(input_text="Revenue starts at 100 and grows 7% annually for 3 years. What is the projected value?")
        )
        self.assertIsNotNone(exact)
        self.assertEqual(exact.answer, "122.5043")

    def test_solves_logic_families_with_unique_proofs(self) -> None:
        cases = {
            "Mia is younger than Noah. Noah is younger than Omar. Who is the oldest? Return only the name.": (
                "Omar",
                ProofType.ORDERING,
            ),
            (
                "Ana, Bruno, and Carla each own one different pet: cat, dog, or bird. "
                "Ana does not own the bird. Bruno owns the dog. Who owns the cat? Return only the name."
            ): ("Ana", ProofType.FINITE_ASSIGNMENT),
            "If the alarm is armed, the door locks. The alarm is armed. Is the door locked? Return exactly yes or no.": (
                "yes",
                ProofType.PROPOSITIONAL,
            ),
            "If a file is signed, upload is accepted. Upload is not accepted. Is the file signed? Return exactly yes or no.": (
                "no",
                ProofType.PROPOSITIONAL,
            ),
            "All borks are nims. No nims are zeds. Can a bork be a zed? Return exactly yes or no.": (
                "no",
                ProofType.QUANTIFIED,
            ),
            "All merls are tivas. Some tivas are roons. Is it guaranteed that some merls are roons? Return exactly yes or no.": (
                "no",
                ProofType.QUANTIFIED,
            ),
        }
        for prompt, (answer, proof_type) in cases.items():
            with self.subTest(prompt=prompt):
                solved = solve_with_proof(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(solved)
                self.assertEqual(solved.answer, answer)
                self.assertEqual(solved.proof.proof_type, proof_type)

    def test_ordering_proof_accepts_descriptor_and_identify_queries_only_for_unique_extremes(self) -> None:
        cases = {
            (
                "Four brothers (Liam, Mason, Noah, Oliver) have different ages. "
                "Liam is older than Mason. Mason is older than Noah. Noah is older than Oliver. "
                "Who is the youngest brother? Output only the name in all capital letters."
            ): "Oliver",
            (
                "Five people (A, B, C, D, and E) have different heights. "
                "A is taller than B. B is taller than C. C is taller than D. D is taller than E. "
                "Identify the shortest person? Return only the uppercase letter."
            ): "E",
        }
        for prompt, expected in cases.items():
            with self.subTest(prompt=prompt):
                solved = solve_with_proof(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(solved)
                self.assertEqual(solved.answer, expected)
                self.assertEqual(solved.proof.proof_type, ProofType.ORDERING)
                self.assertTrue(solved.proof.unique)

        second_tallest = (
            "Alice is taller than Bob. David is taller than Alice but shorter than Charlie. "
            "Who is the second tallest sibling?"
        )
        self.assertIsNone(solve_with_proof(TaskEnvelope(input_text=second_tallest)))

    def test_rejects_inconsistent_or_underdetermined_logic(self) -> None:
        blocked = [
            "Mia is older than Noah. Noah is older than Mia. Who is the oldest? Return only the name.",
            "Mia is older than Noah. Pia is older than Quinn. Who is the oldest? Return only the name.",
            (
                "Ana, Bruno, and Carla each own one different pet: cat, dog, or bird. "
                "Ana does not own the bird. Who owns the cat? Return only the name."
            ),
            "If the alarm is armed, the door locks. The alarm is not armed. Is the door locked? Return exactly yes or no.",
        ]
        for prompt in blocked:
            with self.subTest(prompt=prompt):
                self.assertIsNone(solve_with_proof(TaskEnvelope(input_text=prompt)))

        ordering = attempt_proof(TaskEnvelope(input_text=blocked[0]))
        assignment = attempt_proof(TaskEnvelope(input_text=blocked[2]))
        converse = attempt_proof(TaskEnvelope(input_text=blocked[3]))
        self.assertEqual(ordering.rejection_reason, "inconsistent_or_underdetermined_ordering")
        self.assertTrue(ordering.counterexamples)
        self.assertEqual(assignment.rejection_reason, "non_unique_finite_assignment")
        self.assertTrue(assignment.counterexamples)
        self.assertEqual(converse.rejection_reason, "unsupported_or_invalid_propositional_inference")
        self.assertTrue(converse.counterexamples)

    def test_records_specific_math_rejection_reasons(self) -> None:
        mismatch = attempt_proof(TaskEnvelope(input_text="Convert 2 meters to kilograms. Return only the number."))
        unsafe = attempt_proof(TaskEnvelope(input_text="Calculate __import__('os').system('id'). Return only the number."))
        inexact = attempt_proof(TaskEnvelope(input_text="Calculate 1 / 3. Return only the number."))

        self.assertEqual(mismatch.rejection_reason, "unit_dimension_mismatch")
        self.assertTrue(mismatch.counterexamples)
        self.assertEqual(unsafe.rejection_reason, "unsafe_expression")
        self.assertEqual(inexact.rejection_reason, "inexact_result_requires_rounding_instruction")

    def test_candidate_must_match_recomputed_proof_and_answer_contract(self) -> None:
        task = TaskEnvelope(input_text="What is 15% of 240? Return only the number.")

        accepted = verify_candidate_against_proof(task, "The answer is 36.")
        rejected = verify_candidate_against_proof(task, "The answer is 35.")
        ambiguous = verify_candidate_against_proof(task, "It is either 35 or 36.")

        self.assertTrue(accepted.accepted)
        self.assertEqual(accepted.canonical_candidate, "36")
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.reason, "candidate_disagrees_with_verified_proof")
        self.assertFalse(ambiguous.accepted)
        self.assertTrue(ambiguous.reason.startswith("answer_contract:"))

    def test_promoted_policy_pins_current_evidence(self) -> None:
        policy = json.loads(Path("configs/proof-verifier-policy-v1.json").read_text(encoding="utf-8"))

        self.assertTrue(policy["default_enabled"])
        for key in ("dataset", "engine"):
            path = Path(policy["evidence"][f"{key}_path"])
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, policy["evidence"][f"{key}_sha256"])
        evaluation = json.loads(Path(policy["evidence"]["evaluation_path"]).read_text(encoding="utf-8"))
        gate = policy["evidence"]["evaluation_gate"]
        self.assertGreaterEqual(evaluation["summary"]["released"], gate["minimum_released"])
        self.assertGreaterEqual(
            evaluation["summary"]["released_wilson_lower_95"],
            gate["minimum_wilson_lower_95"],
        )
        self.assertEqual(evaluation["summary"].get("false_positive", 0), gate["required_false_positives"])


if __name__ == "__main__":
    unittest.main()
