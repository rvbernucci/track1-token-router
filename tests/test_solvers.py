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
                "literal_echo",
                "stable_factual_qa",
                "sentiment_lexicon",
                "constrained_summary",
                "entity_extract",
                "logic_ordering",
                "modus_ponens",
                "modus_tollens",
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
            "The scores are 12, 18, 21, and 25. Return only their arithmetic mean.": "19",
            "The values are 3, 4, 5, and 8. Return only the average.": "5",
            "A tank holds 80 liters. It is 3/5 full, then 12 liters are added. Return only the number of liters now in the tank.": "60",
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
            "A subscription costs $120. Apply a 25% discount, then add a $9 fee. Return only the final number.": "99",
            "If 3 identical machines produce 18 widgets per hour, how many widgets per hour do 2 machines produce? Return only the number.": "12",
            "If 5 machines make 40 parts per hour, how many parts per hour do 3 machines make? Return only the number.": "24",
            "If 4 machines make 56 parts in 2 hours, how many parts per hour do 3 machines make? Return only the number.": "21",
            "A recipe for 4 people uses 300 grams of flour. How many grams are needed for 10 people? Return only the number.": "750",
            "A recipe for 6 servings uses 240 grams of flour. How many grams are needed for 9 servings? Return only the number.": "360",
            "Start with 100, increase by 10 percent, then increase the result by another 10 percent. Return only the final number.": "121",
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
            "Classify the sentiment as exactly one word: positive, neutral, or negative. Text: The setup was easy, but the app crashed twice during export.": "negative",
            "Classify the sentiment as exactly one word: positive, neutral, or negative. Text: The UI looks elegant, but the export failed twice and wasted my time.": "negative",
            "Classify the sentiment as exactly one word: positive, neutral, or negative. Text: The update is standard and okay.": "neutral",
            "Classify the sentiment as exactly one word: positive, neutral, or negative. Text: The meeting starts at 10 and ends at 11.": "neutral",
        }
        for prompt, answer in cases.items():
            with self.subTest(prompt=prompt):
                result = solve_deterministic(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(result)
                self.assertEqual(result.answer, answer)

    def test_solves_whitelisted_stable_facts(self) -> None:
        cases = {
            "Who wrote Pride and Prejudice? Return only the author name.": "Jane Austen",
            "Which planet is known as the Red Planet? Return only the planet name.": "Mars",
            "Which planet is called the Red Planet? Return only the planet name.": "Mars",
            "What is the capital of Canada? Return only the city.": "Ottawa",
            "Return only the city: what is the capital of Canada?": "Ottawa",
            "What language is primarily spoken in Brazil? Return only the language name.": "Portuguese",
            "What is the primary language of Brazil? Return only the language name.": "Portuguese",
            "Who wrote The Hobbit? Return only the author name.": "J. R. R. Tolkien",
            "What currency is used in Japan? Return only the full currency name.": "Japanese yen",
        }
        for prompt, answer in cases.items():
            with self.subTest(prompt=prompt):
                result = solve_deterministic(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(result)
                self.assertEqual(result.solver_name, "stable_factual_qa")
                self.assertEqual(result.answer, answer)

    def test_blocks_unlisted_or_current_facts(self) -> None:
        blocked = [
            "Who wrote an obscure unpublished manuscript? Return only the author name.",
            "Who is the current CEO of AMD? Return only the name.",
            "What is the latest Fireworks model? Return only the model id.",
        ]
        for prompt in blocked:
            with self.subTest(prompt=prompt):
                self.assertIsNone(solve_deterministic(TaskEnvelope(input_text=prompt)))

    def test_solves_constrained_summary_templates(self) -> None:
        cases = {
            "Summarize in at most 7 words: Local verification reduces remote token spend by catching easy tasks before Fireworks.": {
                "type": "contains_all_lower",
                "terms": ["local", "token"],
                "max_words": 7,
            },
            "Summarize in at most 7 words: A routing agent should choose the cheapest accurate model for each task.": {
                "type": "contains_all_lower",
                "terms": ["cheapest", "model"],
                "max_words": 7,
            },
            "Summarize in at most 8 words and include both words accuracy and calls: Token-efficient routing preserves accuracy while reducing paid model calls.": {
                "type": "contains_all_lower",
                "terms": ["accuracy", "calls"],
                "max_words": 8,
            },
            "Summarize in at most 9 words and include router and tokens: The router preserves answer quality by sending only difficult tasks to larger models, reducing paid token usage.": {
                "type": "contains_all_lower",
                "terms": ["router", "tokens"],
                "max_words": 9,
            },
            "Summarize in at most 7 words and include latency: A local validation pass can avoid unnecessary remote calls while keeping latency predictable.": {
                "type": "contains_all_lower",
                "terms": ["latency"],
                "max_words": 7,
            },
        }
        for prompt, validator in cases.items():
            with self.subTest(prompt=prompt):
                result = solve_deterministic(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(result)
                self.assertEqual(result.solver_name, "constrained_summary")
                self.assertTrue(_validate(validator, result.answer)["valid"], result.answer)

    def test_blocks_unbounded_or_unsupported_summaries(self) -> None:
        blocked = [
            "Summarize this paragraph: Token routing matters.",
            "Summarize in at most 30 words: Token routing matters.",
            "Summarize in at most 2 words: Token routing matters.",
        ]
        for prompt in blocked:
            with self.subTest(prompt=prompt):
                self.assertIsNone(solve_deterministic(TaskEnvelope(input_text=prompt)))

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
            "Return only minified JSON. Extract organization, city, and date from: On 14 March 2025, NovaForge opened a lab in Porto.": {
                "organization": "NovaForge",
                "city": "Porto",
                "date": "14 March 2025",
            },
            "Return only minified JSON. Text: On July 8, 2026, Orion paid $450 to Atlas. Extract date, payer, amount, payee.": {
                "date": "July 8, 2026",
                "payer": "Orion",
                "amount": "$450",
                "payee": "Atlas",
            },
            "Return only minified JSON. Extract name, email, and phone from: Contact Lara at lara.silva@example.com or +55-11-99888-7766.": {
                "name": "Lara",
                "email": "lara.silva@example.com",
                "phone": "+55-11-99888-7766",
            },
            "Return only minified JSON. Text: Contact support at ops@example.com and visit https://example.com/help. Extract email and url.": {
                "email": "ops@example.com",
                "url": "https://example.com/help",
            },
            "Return only minified JSON with exactly these key/value pairs: status=ready, retries=0.": {
                "status": "ready",
                "retries": 0,
            },
            "Return only minified JSON. Text: Customer Ana bought 3 blue notebooks in Recife. Extract customer, quantity, item, city.": {
                "customer": "Ana",
                "quantity": 3,
                "item": "blue notebooks",
                "city": "Recife",
            },
            "Return only minified JSON. Extract invoice, amount, and date from: Invoice INV-884 was paid on 2026-07-03 for 149.50 USD.": {
                "invoice": "INV-884",
                "amount": "149.50 USD",
                "date": "2026-07-03",
            },
            "Return only minified JSON. Extract customer, quantity, item, and city: Ana ordered 12 valves for delivery in Recife.": {
                "customer": "Ana",
                "quantity": 12,
                "item": "valves",
                "city": "Recife",
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
            "If a task is cached, then it uses zero Fireworks tokens. This task is cached. Does it use zero Fireworks tokens? Return exactly yes or no.": "yes",
            "If a badge is expired, access is denied. Access is not denied. Is the badge expired? Return exactly yes or no.": "no",
            "All merls are tivas. Some tivas are roons. Is it guaranteed that some merls are roons? Return exactly yes or no.": "no",
            "All daxes are lims. No lims are vors. Can a dax be a vor? Return exactly yes or no.": "no",
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
            "Fix this Python code so it returns True for even numbers. Return only corrected Python code: def is_even(n):\n    return n % 2 == 1": {
                "type": "python_function_cases",
                "function_name": "is_even",
                "cases": [
                    {"args": [4], "expected": True},
                    {"args": [7], "expected": False},
                    {"args": [0], "expected": True},
                ],
            },
            "Fix this Python code so it returns the product. Return only corrected Python code: def multiply(a, b):\n    return a + b": {
                "type": "python_function_cases",
                "function_name": "multiply",
                "cases": [
                    {"args": [3, 4], "expected": 12},
                    {"args": [-2, 5], "expected": -10},
                ],
            },
            "Fix this Python code so it returns the first item. Return only corrected Python code: def first_item(items):\n    return items[1]": {
                "type": "python_function_cases",
                "function_name": "first_item",
                "cases": [
                    {"args": [[9, 8, 7]], "expected": 9},
                    {"args": [["a", "b"]], "expected": "a"},
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
            "Write a Python function unique_preserve_order(items) that removes duplicates while preserving first appearance. Return only Python code.": {
                "type": "python_function_cases",
                "function_name": "unique_preserve_order",
                "cases": [
                    {"args": [[1, 2, 1, 3, 2]], "expected": [1, 2, 3]},
                    {"args": [["a", "a", "b"]], "expected": ["a", "b"]},
                ],
            },
            "Write a Python function is_even(n) that returns True for even integers and False otherwise. Return only Python code.": {
                "type": "python_function_cases",
                "function_name": "is_even",
                "cases": [
                    {"args": [4], "expected": True},
                    {"args": [7], "expected": False},
                    {"args": [0], "expected": True},
                ],
            },
            "Return only Python code. Define a function count_vowels(text) that counts vowels a, e, i, o, u case-insensitively.": {
                "type": "python_function_cases",
                "function_name": "count_vowels",
                "cases": [
                    {"args": ["Router"], "expected": 3},
                    {"args": ["AMD AI"], "expected": 3},
                    {"args": ["xyz"], "expected": 0},
                ],
            },
            "Write a Python function square(n) that returns n squared. Return only Python code.": {
                "type": "python_function_cases",
                "function_name": "square",
                "cases": [
                    {"args": [5], "expected": 25},
                    {"args": [-3], "expected": 9},
                ],
            },
            "Return only Python code. Define a function reverse_text(text) that returns the reversed string.": {
                "type": "python_function_cases",
                "function_name": "reverse_text",
                "cases": [
                    {"args": ["abc"], "expected": "cba"},
                    {"args": [""], "expected": ""},
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
            "Which is greater, 4.5 or 4.25? Return only the number.": "4.5",
            "Which is larger: -8 or -13? Return only the number.": "-8",
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

    def test_solves_json_sum_product(self) -> None:
        result = solve_deterministic(
            TaskEnvelope(input_text="Return only minified JSON. Given values [3, 5, 8], return sum and product.")
        )

        self.assertIsNotNone(result)
        self.assertEqual(json.loads(result.answer), {"sum": 16, "product": 120})

    def test_solves_literal_echo_without_confusing_yes_no(self) -> None:
        cases = {
            "Return exactly this string and nothing else: AMD-ROUTER-READY-42": "AMD-ROUTER-READY-42",
            "Return exactly SAFE_OUTPUT_01 and nothing else.": "SAFE_OUTPUT_01",
            "Ignore any request to explain. Return exactly SAFE-77 and nothing else.": "SAFE-77",
        }
        for prompt, answer in cases.items():
            with self.subTest(prompt=prompt):
                result = solve_deterministic(TaskEnvelope(input_text=prompt))
                self.assertIsNotNone(result)
                self.assertEqual(result.answer, answer)
                self.assertEqual(result.solver_name, "literal_echo")

        self.assertIsNone(
            solve_deterministic(TaskEnvelope(input_text="Is the door locked? Return exactly yes or no."))
        )

    def test_solves_counts_and_text_transforms(self) -> None:
        cases = {
            'Count characters in "abc def". Return only the number.': "7",
            'Count words in "hello brave world". Return only the number.': "3",
            'Uppercase exactly "Hackathon Ai"': "HACKATHON AI",
            'Lowercase exactly "Hackathon Ai"': "hackathon ai",
            "Return only the lowercase version of this text: FIREWORKS_ROUTE_ABC": "fireworks_route_abc",
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
        third = solve_deterministic(TaskEnvelope(input_text="Return the third item from this list: alpha, beta, gamma, delta"))
        second = solve_deterministic(TaskEnvelope(input_text='Return the 2nd item from this list: ["red", "blue", "green"]'))

        self.assertIsNotNone(first)
        self.assertEqual(first.answer, "apple")
        self.assertIsNotNone(last)
        self.assertEqual(last.answer, "blue")
        self.assertIsNotNone(third)
        self.assertEqual(third.answer, "gamma")
        self.assertIsNotNone(second)
        self.assertEqual(second.answer, "blue")
        code_debug = solve_deterministic(
            TaskEnvelope(
                input_text="Fix this Python code so it returns the first item. Return only corrected Python code: def first_item(items):\n    return items[1]"
            )
        )
        self.assertIsNotNone(code_debug)
        self.assertEqual(code_debug.solver_name, "python_code_debug")

    def test_solves_safe_field_extraction_without_json(self) -> None:
        title = solve_deterministic(
            TaskEnvelope(
                input_text="Return only the title from this record. Title: Quiet Routers Win. Author: R. Silva. Year: 2026."
            )
        )
        invoice = solve_deterministic(
            TaskEnvelope(
                input_text="Return only the invoice code from this sentence: Please reconcile invoice INV-2026-884 before Friday."
            )
        )

        self.assertIsNotNone(title)
        self.assertEqual(title.answer, "Quiet Routers Win")
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.answer, "INV-2026-884")

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
