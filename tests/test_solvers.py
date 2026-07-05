import json
import unittest

from router.core.contracts import TaskEnvelope
from router.orchestration.solvers import SOLVERS, solve_deterministic


class SolverPackTests(unittest.TestCase):
    def test_registry_is_explicit(self) -> None:
        names = [solver.name for solver in SOLVERS]

        self.assertEqual(
            names,
            [
                "arithmetic",
                "numeric_compare",
                "char_count",
                "word_count",
                "case_transform",
                "whitespace",
                "json_transform",
                "list_item",
            ],
        )

    def test_solves_safe_integer_arithmetic(self) -> None:
        cases = {
            "What is 6 * 7? Return only the number.": "42",
            "Calculate 18 / 3": "6",
            "Compute 10 - 12": "-2",
            "8 + 9": "17",
        }
        for prompt, answer in cases.items():
            with self.subTest(prompt=prompt):
                result = solve_deterministic(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(result)
                self.assertEqual(result.answer, answer)
                self.assertEqual(result.confidence, "high")

    def test_blocks_unsafe_or_complex_arithmetic(self) -> None:
        blocked = [
            "What is 10 / 4? Return only the number.",
            "What is 10 / 0? Return only the number.",
            "What is 12 * 5 + 3?",
            "A workshop makes 6 parts per hour for 4 hours, then discards 2. Return only the final count.",
            "Solve for x: 2x + 1 = 5",
        ]
        for prompt in blocked:
            with self.subTest(prompt=prompt):
                self.assertIsNone(solve_deterministic(TaskEnvelope(input_text=prompt)))

    def test_solves_numeric_compare(self) -> None:
        cases = {
            "Choose the larger number and return only it: 10 or 12.": "12",
            "Which is smaller, -4 or 3? Return only the number.": "-4",
        }
        for prompt, answer in cases.items():
            result = solve_deterministic(TaskEnvelope(input_text=prompt))
            self.assertIsNotNone(result)
            self.assertEqual(result.answer, answer)

    def test_solves_counts_and_text_transforms(self) -> None:
        cases = {
            'Count characters in "abc def". Return only the number.': "7",
            'Count words in "hello brave world". Return only the number.': "3",
            'Uppercase exactly "Hackathon Ai"': "HACKATHON AI",
            'Lowercase exactly "Hackathon Ai"': "hackathon ai",
            'Titlecase exactly "hello brave world"': "Hello Brave World",
            'Trim whitespace exactly "  hello  "': "hello",
            'Normalize whitespace exactly "a   b\nc"': "a b c",
        }
        for prompt, answer in cases.items():
            with self.subTest(prompt=prompt):
                result = solve_deterministic(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(result)
                self.assertEqual(result.answer, answer)

    def test_solves_json_transforms(self) -> None:
        compact = solve_deterministic(TaskEnvelope(input_text='Compact JSON: {"b":2, "a":1}'))
        pretty = solve_deterministic(TaskEnvelope(input_text='Pretty JSON: {"b":2, "a":1}'))

        self.assertIsNotNone(compact)
        self.assertEqual(compact.answer, '{"a":1,"b":2}')
        self.assertIsNotNone(pretty)
        self.assertEqual(json.loads(pretty.answer), {"a": 1, "b": 2})
        self.assertIn("\n", pretty.answer)

    def test_solves_first_and_last_item(self) -> None:
        first = solve_deterministic(TaskEnvelope(input_text="Return the first item from this list: apple, banana, cherry"))
        last = solve_deterministic(TaskEnvelope(input_text='Return the last item from this list: ["red", "blue"]'))

        self.assertIsNotNone(first)
        self.assertEqual(first.answer, "apple")
        self.assertIsNotNone(last)
        self.assertEqual(last.answer, "blue")

    def test_blocks_ambiguous_dates_and_invalid_json(self) -> None:
        blocked = [
            "What is the date tomorrow?",
            "Compact JSON: {not valid}",
            "Return the first item after sorting this list: banana, apple",
            "Count characters in this unquoted string please",
        ]
        for prompt in blocked:
            with self.subTest(prompt=prompt):
                self.assertIsNone(solve_deterministic(TaskEnvelope(input_text=prompt)))


if __name__ == "__main__":
    unittest.main()
