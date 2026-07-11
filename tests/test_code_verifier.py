import hashlib
import json
from pathlib import Path
import unittest

from router.core.contracts import TaskEnvelope
from router.orchestration.code_verifier import (
    CodeBehavior,
    infer_code_task_contract,
    verify_code_candidate,
)


class CodeVerifierTests(unittest.TestCase):
    def test_extracts_supported_contracts(self) -> None:
        cases = {
            "Write only a Python function named add(a, b) that returns their sum.": CodeBehavior.ADD,
            "Write a Python function square(x) that returns x squared.": CodeBehavior.SQUARE,
            "Write a Python function second_largest(numbers) handling duplicates correctly.": CodeBehavior.SECOND_LARGEST,
            "Write a Python function unique_preserve_order(items) that removes duplicates preserving order.": CodeBehavior.UNIQUE_PRESERVE_ORDER,
            "Write a Python function normalize_slug(text) that lowercases text and uses hyphens.": CodeBehavior.NORMALIZE_SLUG,
            "Write a Python function is_palindrome(text) that detects a palindrome.": CodeBehavior.PALINDROME,
        }
        for prompt, behavior in cases.items():
            with self.subTest(prompt=prompt):
                contract = infer_code_task_contract(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(contract)
                self.assertEqual(contract.behavior, behavior)

    def test_malformed_signature_abstains_instead_of_raising(self) -> None:
        task = TaskEnvelope(input_text="Write Python add(a + b) that returns their sum.")
        self.assertIsNone(infer_code_task_contract(task))

    def test_accepts_correct_code_and_unwraps_markdown(self) -> None:
        task = TaskEnvelope(input_text="Write only a Python function named add(a, b) that returns their sum.")
        report = verify_code_candidate(task, "```python\ndef add(a, b):\n    return a + b\n```")

        self.assertTrue(report.accepted)
        self.assertTrue(report.static_passed)
        self.assertTrue(report.dynamic_passed)
        self.assertEqual(report.tests_passed, report.tests_run)
        self.assertEqual(report.properties_passed, report.properties_run)

    def test_debugging_requires_original_to_fail_and_candidate_to_pass(self) -> None:
        task = TaskEnvelope(
            input_text=(
                "This Python function should return the max of a list but has a bug:\n"
                "```python\ndef get_max(nums):\n    return nums[0]\n```\n"
                "Find and fix it. Return only corrected Python code."
            )
        )
        fixed = verify_code_candidate(task, "def get_max(nums):\n    return max(nums)")

        self.assertTrue(fixed.accepted)
        self.assertTrue(fixed.original_failed)

    def test_rejects_static_escape_primitives(self) -> None:
        task = TaskEnvelope(input_text="Write only a Python function named add(a, b) that returns their sum.")
        candidates = [
            "import os\ndef add(a, b):\n    return a + b",
            "def add(a, b):\n    return open('/tmp/x', 'w')",
            "def add(a, b):\n    return __import__('os').system('id')",
            "x = 1\ndef add(a, b):\n    return a + b",
            "def add(a, b):\n    return (a).__class__",
        ]
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                report = verify_code_candidate(task, candidate)
                self.assertFalse(report.accepted)
                self.assertFalse(report.static_passed)

    def test_rejects_wrong_signature_placeholder_and_extra_functions(self) -> None:
        task = TaskEnvelope(input_text="Write only a Python function named add(a, b) that returns their sum.")
        candidates = [
            "def add(a):\n    return a",
            "def add(a, b=0):\n    return a + b",
            "def add(a, b):\n    pass",
            "def helper(x):\n    return x\n\ndef add(a, b):\n    return helper(a) + b",
        ]
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                self.assertFalse(verify_code_candidate(task, candidate).accepted)

    def test_bounds_literal_size_before_execution(self) -> None:
        task = TaskEnvelope(input_text="Write only a Python function named add(a, b) that returns their sum.")
        candidate = "def add(a, b):\n    marker = " + repr("x" * 4_097) + "\n    return a + b"

        report = verify_code_candidate(task, candidate)

        self.assertFalse(report.accepted)
        self.assertIn("literal_size_limit", report.rejection_reasons)

    def test_properties_kill_plausible_mutants(self) -> None:
        cases = [
            (
                "Write only a Python function named add(a, b) that returns their sum.",
                "def add(a, b):\n    return abs(a) + abs(b)",
            ),
            (
                "Write a Python function second_largest(numbers) that handles duplicates correctly.",
                "def second_largest(numbers):\n    return sorted(numbers)[-2]",
            ),
            (
                "Write a Python function unique_preserve_order(items) that removes duplicates preserving order.",
                "def unique_preserve_order(items):\n    return list(set(items))",
            ),
            (
                "Write a Python function normalize_slug(text) that lowercases text, trims spaces, and replaces spaces with hyphens.",
                "def normalize_slug(text):\n    return text.lower().replace(' ', '-')",
            ),
        ]
        for prompt, candidate in cases:
            with self.subTest(prompt=prompt):
                report = verify_code_candidate(TaskEnvelope(input_text=prompt), candidate)
                self.assertFalse(report.accepted)
                self.assertTrue(report.static_passed)
                self.assertFalse(report.dynamic_passed)

    def test_infinite_loop_is_contained_by_timeout(self) -> None:
        task = TaskEnvelope(input_text="Write only a Python function named add(a, b) that returns their sum.")
        report = verify_code_candidate(task, "def add(a, b):\n    while True:\n        pass", timeout_s=0.2)

        self.assertFalse(report.accepted)
        self.assertIn(report.rejection_reasons[0], {"execution_timeout", "worker_exit:-24", "worker_exit:-9"})

    def test_unsupported_language_or_behavior_refuses(self) -> None:
        unsupported = [
            "Write a JavaScript function add(a, b).",
            "Write a Python web server.",
        ]
        for prompt in unsupported:
            with self.subTest(prompt=prompt):
                report = verify_code_candidate(TaskEnvelope(input_text=prompt), "def add(a, b):\n    return a + b")
                self.assertFalse(report.accepted)
                self.assertIn("unsupported_or_ambiguous_contract", report.rejection_reasons)

    def test_promoted_policy_pins_current_evidence(self) -> None:
        policy = json.loads(Path("configs/code-verifier-policy-v1.json").read_text(encoding="utf-8"))

        self.assertTrue(policy["default_enabled"])
        for key in ("dataset", "engine"):
            path = Path(policy["evidence"][f"{key}_path"])
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                policy["evidence"][f"{key}_sha256"],
            )
        evaluation = json.loads(Path(policy["evidence"]["evaluation_path"]).read_text(encoding="utf-8"))
        gate = policy["evidence"]["evaluation_gate"]
        self.assertGreaterEqual(evaluation["summary"]["accepted"], gate["minimum_accepted"])
        self.assertGreaterEqual(evaluation["summary"]["mutation_score"], gate["minimum_mutation_score"])
        self.assertGreaterEqual(
            evaluation["summary"]["adversarial_containment_rate"],
            gate["minimum_adversarial_containment_rate"],
        )
        self.assertEqual(evaluation["summary"].get("false_positive", 0), gate["required_false_positives"])


if __name__ == "__main__":
    unittest.main()
