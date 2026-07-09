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
                "percent_fee_math",
                "proportional_rate",
                "numeric_compare",
                "sentiment_lexicon",
                "entity_extract",
                "logic_ordering",
                "modus_ponens",
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
