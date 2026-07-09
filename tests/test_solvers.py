import json
import unittest

from router.core.contracts import TaskEnvelope
from router.orchestration.solvers import SOLVERS, solve_deterministic
from scripts.fireworks_microbench import _validate


class SolverPackTests(unittest.TestCase):
    def test_registry_is_explicit(self) -> None:
        names = [solver.name for solver in SOLVERS]

        self.assertEqual(
            names,
            [
                "arithmetic",
                "percent_fee_math",
                "proportional_rate",
                "numeric_compare",
                "sentiment_lexicon",
                "entity_extract",
                "logic_ordering",
                "modus_ponens",
                "python_code_debug",
                "python_code_generation",
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
            "Compute 17 * 6 + 4. Return only the number.": "106",
            "Evaluate (8 + 4) / 3. Return only the number.": "4",
            "8 + 9": "17",
        }
        for prompt, answer in cases.items():
            with self.subTest(prompt=prompt):
                result = solve_deterministic(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(result)
                self.assertEqual(result.answer, answer)
                self.assertEqual(result.confidence, "high")

    def test_solves_safe_percent_and_rate_math(self) -> None:
        cases = {
            "A plan costs 80. It receives a 15 percent discount and then a 5 fee is added. Return only the final number.": "73",
            "If 3 identical machines produce 18 widgets per hour, how many widgets per hour do 2 machines produce? Return only the number.": "12",
        }
        for prompt, answer in cases.items():
            with self.subTest(prompt=prompt):
                result = solve_deterministic(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(result)
                self.assertEqual(result.answer, answer)

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

    def test_solves_explicit_sentiment(self) -> None:
        cases = {
            "Classify the sentiment as exactly one word: positive, neutral, or negative. Text: The interface is quick, clean, and reliable.": "positive",
            "Classify the sentiment as exactly one word: positive, neutral, or negative. Text: The deployment failed twice and the logs were confusing.": "negative",
            "Classify the sentiment as exactly one word: positive, neutral, or negative. Text: The update is standard and okay.": "neutral",
        }
        for prompt, answer in cases.items():
            with self.subTest(prompt=prompt):
                result = solve_deterministic(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(result)
                self.assertEqual(result.answer, answer)

    def test_blocks_ambiguous_sentiment(self) -> None:
        blocked = [
            "Classify the sentiment as exactly one word: positive, neutral, or negative. Text: It is good but also confusing.",
            "Is this positive or negative? Text: maybe.",
            "Classify tone: The interface is reliable.",
        ]
        for prompt in blocked:
            with self.subTest(prompt=prompt):
                self.assertIsNone(solve_deterministic(TaskEnvelope(input_text=prompt)))

    def test_solves_structured_entity_extraction(self) -> None:
        cases = {
            "Return only minified JSON. Text: Ana Ribeiro founded Nova Labs in Recife. Extract person, organization, city.": {
                "person": "Ana Ribeiro",
                "organization": "Nova Labs",
                "city": "Recife",
            },
            "Return only minified JSON. Text: On July 8, 2026, Orion paid $450 to Atlas. Extract date, payer, amount, payee.": {
                "date": "July 8, 2026",
                "payer": "Orion",
                "amount": "$450",
                "payee": "Atlas",
            },
            "Return only minified JSON. Text: Contact support at ops@example.com and visit https://example.com/help. Extract email and url.": {
                "email": "ops@example.com",
                "url": "https://example.com/help",
            },
            "Extract the names from this sentence as minified JSON with key names: Ana met Bruno in Recife.": {
                "names": ["Ana", "Bruno"],
            },
        }
        for prompt, expected in cases.items():
            with self.subTest(prompt=prompt):
                result = solve_deterministic(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(result)
                self.assertEqual(json.loads(result.answer), expected)

    def test_blocks_ambiguous_entity_extraction(self) -> None:
        blocked = [
            "Extract named entities from: ana founded nova labs.",
            "Return only minified JSON. Text: Ana may join Nova Labs. Extract person, organization, city.",
            "Text: On July 8, 2026, Orion paid Atlas. Extract date, payer, amount, payee.",
        ]
        for prompt in blocked:
            with self.subTest(prompt=prompt):
                self.assertIsNone(solve_deterministic(TaskEnvelope(input_text=prompt)))

    def test_solves_simple_logic_patterns(self) -> None:
        cases = {
            "Ava is taller than Bea. Bea is taller than Cora. Who is the shortest? Return only the name.": "Cora",
            "Ava is taller than Bea. Bea is taller than Cora. Who is the tallest? Return only the name.": "Ava",
            "If the alarm is armed, the door locks. The alarm is armed. Is the door locked? Return exactly yes or no.": "yes",
            "All merls are tivas. Some tivas are roons. Is it guaranteed that some merls are roons? Return exactly yes or no.": "no",
            "All daxes are wugs. No wugs are plims. Can a daxes be a plims? Return exactly yes or no.": "no",
        }
        for prompt, answer in cases.items():
            with self.subTest(prompt=prompt):
                result = solve_deterministic(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(result)
                self.assertEqual(result.answer, answer)

    def test_blocks_ambiguous_logic_patterns(self) -> None:
        blocked = [
            "Ava is taller than Bea. Cora is taller than Dani. Who is the shortest?",
            "If the alarm is armed, the door locks. The alarm is not armed. Is the door locked?",
            "If it rains, the ground is wet. The ground is wet. Did it rain?",
        ]
        for prompt in blocked:
            with self.subTest(prompt=prompt):
                self.assertIsNone(solve_deterministic(TaskEnvelope(input_text=prompt)))

    def test_solves_safe_python_debug_templates(self) -> None:
        cases = {
            "Fix this Python code so it returns the sum. Return only corrected Python code: def add(a, b):\n    return a - b": {
                "type": "python_function_cases",
                "function_name": "add",
                "cases": [
                    {"args": [2, 3], "expected": 5},
                    {"args": [-4, 10], "expected": 6},
                ],
            },
            "Return only corrected Python code. Debug this function so it checks every item: def first_even(nums):\n    for i in range(1, len(nums)):\n        if nums[i] % 2 == 0:\n            return nums[i]\n    return None": {
                "type": "python_function_cases",
                "function_name": "first_even",
                "cases": [
                    {"args": [[2, 3, 5]], "expected": 2},
                    {"args": [[1, 4, 6]], "expected": 4},
                    {"args": [[1, 3, 5]], "expected": None},
                ],
            },
            "Return only corrected Python code. Debug this function so age 18 counts as adult: def is_adult(age):\n    return age > 18": {
                "type": "python_function_cases",
                "function_name": "is_adult",
                "cases": [
                    {"args": [18], "expected": True},
                    {"args": [17], "expected": False},
                    {"args": [21], "expected": True},
                ],
            },
        }
        for prompt, validator in cases.items():
            with self.subTest(prompt=prompt):
                result = solve_deterministic(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(result)
                self.assertEqual(result.solver_name, "python_code_debug")
                self.assertTrue(_validate(validator, result.answer)["valid"])

    def test_solves_safe_python_generation_templates(self) -> None:
        cases = {
            "Write a Python function add(a, b) that returns the sum. Return only Python code.": {
                "type": "python_function_cases",
                "function_name": "add",
                "cases": [
                    {"args": [2, 3], "expected": 5},
                    {"args": [-4, 10], "expected": 6},
                ],
            },
            "Return only Python code. Define a function clamp(value, low, high) that returns value bounded inclusively between low and high.": {
                "type": "python_function_cases",
                "function_name": "clamp",
                "cases": [
                    {"args": [5, 1, 10], "expected": 5},
                    {"args": [-3, 0, 10], "expected": 0},
                    {"args": [22, 0, 10], "expected": 10},
                ],
            },
            "Return only Python code. Define a function unique_preserve_order(items) that removes duplicates while preserving first occurrence order.": {
                "type": "python_function_cases",
                "function_name": "unique_preserve_order",
                "cases": [
                    {"args": [["a", "b", "a", "c", "b"]], "expected": ["a", "b", "c"]},
                    {"args": [[3, 3, 2, 1, 2]], "expected": [3, 2, 1]},
                ],
            },
            "Return only Python code. Define a function is_palindrome(text) that ignores case and non-alphanumeric characters and returns a boolean.": {
                "type": "python_function_cases",
                "function_name": "is_palindrome",
                "cases": [
                    {"args": ["A man, a plan, a canal: Panama"], "expected": True},
                    {"args": ["router"], "expected": False},
                    {"args": ["No lemon, no melon"], "expected": True},
                ],
            },
            "Return only Python code. Define a function parse_ints(text) that returns all signed integers in the text as a list of ints, in order.": {
                "type": "python_function_cases",
                "function_name": "parse_ints",
                "cases": [
                    {"args": ["a -2 b 10 c 0"], "expected": [-2, 10, 0]},
                    {"args": ["none"], "expected": []},
                    {"args": ["x7y -8"], "expected": [7, -8]},
                ],
            },
        }
        for prompt, validator in cases.items():
            with self.subTest(prompt=prompt):
                result = solve_deterministic(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(result)
                self.assertEqual(result.solver_name, "python_code_generation")
                self.assertTrue(_validate(validator, result.answer)["valid"])

    def test_blocks_unknown_python_code_templates(self) -> None:
        blocked = [
            "Return only Python code. Define a function sort_items(items) that sorts the list.",
            "Return only corrected Python code. Debug this function: def f(x):\n    return x + 1",
            "Define a function clamp(value, low, high).",
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

    def test_solves_json_minmax(self) -> None:
        result = solve_deterministic(
            TaskEnvelope(input_text="Return only minified JSON. Given values [17, 4, 23, 9], return min and max.")
        )

        self.assertIsNotNone(result)
        self.assertEqual(json.loads(result.answer), {"min": 4, "max": 23})

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
