import json
import unittest

from router.core.contracts import AnswerResult, TaskEnvelope
from router.orchestration.final_validator import (
    AnswerContractKind,
    apply_answer_contract,
    finalize_answer_result,
    infer_answer_contract,
)
from router.orchestration.prompt_packet import infer_expected_format


class AnswerContractEngineTests(unittest.TestCase):
    def test_extracts_one_unambiguous_sentiment_label(self) -> None:
        task = TaskEnvelope(input_text="Classify sentiment. Answer exactly one label: positive, negative, or neutral.")

        result = apply_answer_contract(task, "The sentiment is positive.")

        self.assertTrue(result.valid)
        self.assertEqual(result.answer, "positive")
        self.assertEqual(result.actions, ("extracted_unique_label",))

    def test_preserves_sentiment_explanation_when_prompt_requires_a_reason(self) -> None:
        task = TaskEnvelope(
            input_text=(
                "Classify the sentiment as Positive, Negative, or Neutral and give a one-sentence reason: "
                "'The package was damaged, but support resolved the problem.'"
            )
        )
        answer = "Positive, because the initial problem was resolved quickly by support."

        result = apply_answer_contract(task, answer)

        self.assertTrue(result.valid)
        self.assertEqual(result.contract.kind, AnswerContractKind.FREE_TEXT)
        self.assertEqual(result.answer, answer)

    def test_rejects_ambiguous_or_negated_label(self) -> None:
        task = TaskEnvelope(input_text="Classify sentiment. Answer exactly one label: positive, negative, or neutral.")

        ambiguous = apply_answer_contract(task, "It may be positive or neutral.")
        negated = apply_answer_contract(task, "It is not positive.")

        self.assertFalse(ambiguous.valid)
        self.assertTrue(ambiguous.ambiguous)
        self.assertFalse(negated.valid)
        self.assertTrue(negated.ambiguous)

    def test_repairs_json_wrapper_and_enforces_exact_keys(self) -> None:
        task = TaskEnvelope(
            input_text='Return only valid JSON with exactly these keys: "person", "organization", "location".'
        )

        valid = apply_answer_contract(
            task,
            '```json\n{"person":"Ana","organization":"Orion","location":"Recife"}\n```',
        )
        extra = apply_answer_contract(
            task,
            '{"person":"Ana","organization":"Orion","location":"Recife","date":"today"}',
        )

        self.assertTrue(valid.valid)
        self.assertEqual(json.loads(valid.answer)["person"], "Ana")
        self.assertFalse(extra.valid)
        self.assertEqual(extra.reason, "json_keys_mismatch")

    def test_rejects_duplicate_keys_and_nonstandard_json_constants(self) -> None:
        task = TaskEnvelope(input_text='Return only valid JSON with exactly this key: "answer".')

        duplicate = apply_answer_contract(task, '{"answer":1,"answer":2}')
        non_finite = apply_answer_contract(task, '{"answer":NaN}')

        self.assertFalse(duplicate.valid)
        self.assertEqual(duplicate.reason, "invalid_json")
        self.assertFalse(non_finite.valid)
        self.assertEqual(non_finite.reason, "invalid_json")

    def test_canonicalizes_only_bijective_json_key_case(self) -> None:
        task = TaskEnvelope(
            input_text='Return only valid JSON with exactly these keys: "person", "location".'
        )

        result = apply_answer_contract(task, '{"Person":"Ana","Location":"Recife"}')
        collision = apply_answer_contract(task, '{"person":"Ana","Person":"Maya","location":"Recife"}')

        self.assertTrue(result.valid)
        self.assertEqual(json.loads(result.answer), {"person": "Ana", "location": "Recife"})
        self.assertIn("canonicalized_json_key_case", result.actions)
        self.assertFalse(collision.valid)

    def test_unwraps_only_unambiguous_singleton_json_object_array(self) -> None:
        task = TaskEnvelope(
            input_text='Return only valid JSON with exactly these keys: "person", "location".'
        )
        array_task = TaskEnvelope(
            input_text='Return a JSON array with exactly these keys: "person", "location".'
        )
        answer = '[{"person":"Ana","location":"Recife"}]'

        result = apply_answer_contract(task, answer)
        preserved = apply_answer_contract(array_task, answer)

        self.assertTrue(result.valid)
        self.assertEqual(json.loads(result.answer), {"person": "Ana", "location": "Recife"})
        self.assertIn("unwrapped_singleton_json_object_array", result.actions)
        self.assertFalse(preserved.valid)

    def test_singular_json_key_does_not_treat_quoted_value_as_another_key(self) -> None:
        task = TaskEnvelope(input_text='Return only JSON with key "answer" set to "yes".')

        result = apply_answer_contract(task, '{"answer":"yes"}')

        self.assertTrue(result.valid)
        self.assertEqual(result.contract.json_keys, ("answer",))

    def test_unwraps_singleton_arrays_for_singular_exact_json_keys(self) -> None:
        task = TaskEnvelope(
            input_text='Return only valid JSON with exactly these keys: "person", "organization", "location".'
        )

        result = apply_answer_contract(
            task,
            '{"person":["Maya Chen"],"organization":["Harbor Analytics"],"location":["Nairobi"]}',
        )

        self.assertTrue(result.valid)
        self.assertEqual(
            json.loads(result.answer),
            {"person": "Maya Chen", "organization": "Harbor Analytics", "location": "Nairobi"},
        )
        self.assertIn("unwrapped_singleton_json_values", result.actions)

    def test_preserves_json_arrays_when_the_contract_requests_them(self) -> None:
        explicit_array = TaskEnvelope(input_text='Return JSON arrays with exactly these keys: "person", "location".')
        plural_key = TaskEnvelope(input_text='Return JSON with exactly this key: "people".')

        explicit = apply_answer_contract(explicit_array, '{"person":["Ana"],"location":["Recife"]}')
        plural = apply_answer_contract(plural_key, '{"people":["Ana"]}')

        self.assertEqual(json.loads(explicit.answer)["person"], ["Ana"])
        self.assertEqual(json.loads(plural.answer)["people"], ["Ana"])
        self.assertNotIn("unwrapped_singleton_json_values", explicit.actions)
        self.assertNotIn("unwrapped_singleton_json_values", plural.actions)

    def test_preserves_multi_value_json_arrays(self) -> None:
        task = TaskEnvelope(input_text='Return only valid JSON with exactly this key: "person".')

        result = apply_answer_contract(task, '{"person":["Ana","Maya"]}')

        self.assertEqual(json.loads(result.answer)["person"], ["Ana", "Maya"])
        self.assertNotIn("unwrapped_singleton_json_values", result.actions)

    def test_extracts_one_json_array_but_rejects_multiple_json_values(self) -> None:
        task = TaskEnvelope(input_text="Return only valid JSON containing the extracted entities.")

        one = apply_answer_contract(task, 'Result: [{"name":"Ana"},{"name":"Maya"}]')
        multiple = apply_answer_contract(task, 'Candidates: {"name":"Ana"} or {"name":"Maya"}')

        self.assertTrue(one.valid)
        self.assertEqual(json.loads(one.answer), [{"name": "Ana"}, {"name": "Maya"}])
        self.assertFalse(multiple.valid)
        self.assertTrue(multiple.ambiguous)

    def test_extracts_only_one_numeric_candidate(self) -> None:
        task = TaskEnvelope(input_text="What is 12 - 5? Return only the number.")

        valid = apply_answer_contract(task, "The answer is 7.")
        ambiguous = apply_answer_contract(task, "12 minus 5 equals 7.")

        self.assertTrue(valid.valid)
        self.assertEqual(valid.answer, "7")
        self.assertFalse(ambiguous.valid)
        self.assertTrue(ambiguous.ambiguous)

    def test_enforces_sentence_and_word_constraints_without_truncating(self) -> None:
        sentence_task = TaskEnvelope(input_text="Summarize this text in exactly one sentence.")
        word_task = TaskEnvelope(input_text="Describe the result in at most 3 words.")

        self.assertTrue(apply_answer_contract(sentence_task, "Revenue increased strongly.").valid)
        self.assertEqual(
            apply_answer_contract(sentence_task, "Revenue increased. Costs declined.").reason,
            "exact_sentence_count_mismatch",
        )
        self.assertEqual(
            apply_answer_contract(word_task, "Revenue increased very strongly").reason,
            "maximum_word_count_exceeded",
        )

    def test_enforces_maximum_item_constraint_without_truncating(self) -> None:
        task = TaskEnvelope(input_text="Summarize the findings in at most two bullet points.")

        valid = apply_answer_contract(task, "- First\n- Second")
        invalid = apply_answer_contract(task, "- First\n- Second\n- Third")

        self.assertTrue(valid.valid)
        self.assertEqual(invalid.reason, "maximum_item_count_exceeded")

    def test_normalizes_one_unambiguous_formatted_number(self) -> None:
        task = TaskEnvelope(input_text="Calculate the total. Return only the number.")

        grouped = apply_answer_contract(task, "The answer is +1,250.50.")
        scientific = apply_answer_contract(task, "The answer is 1.2e-3.")
        ambiguous = apply_answer_contract(task, "It is either 12 or 13.")

        self.assertEqual(grouped.answer, "1250.50")
        self.assertEqual(scientific.answer, "1.2e-3")
        self.assertFalse(ambiguous.valid)
        self.assertTrue(ambiguous.ambiguous)

    def test_recognizes_natural_code_generation_instruction_and_removes_fence(self) -> None:
        task = TaskEnvelope(input_text="Write only a Python function named add(a, b) that returns their sum.")

        result = apply_answer_contract(task, "```python\ndef add(a, b):\n    return a + b\n```")

        self.assertEqual(infer_expected_format(task), "code")
        self.assertTrue(result.valid)
        self.assertEqual(result.answer, "def add(a, b):\n    return a + b")

    def test_eight_category_contract_matrix_preserves_semantic_boundary(self) -> None:
        cases = [
            (
                "factual_qa",
                "What process causes plants to convert light into chemical energy?",
                "Photosynthesis converts light into chemical energy.",
                "Photosynthesis converts light into chemical energy.",
            ),
            ("math_reasoning", "What is 12 * 4? Return only the number.", "The answer is 48.", "48"),
            (
                "sentiment",
                "Classify sentiment. Answer exactly one label: positive, negative, or neutral.",
                "The label is negative.",
                "negative",
            ),
            (
                "summarization",
                "Summarize the report in exactly one sentence.",
                "Revenue rose while costs declined.",
                "Revenue rose while costs declined.",
            ),
            (
                "ner",
                'Extract entities. Return only valid JSON with exactly these keys: "person", "location".',
                '{"person":["Ana"],"location":["Recife"]}',
                '{"person":"Ana","location":"Recife"}',
            ),
            (
                "code_debugging",
                "Debug the Python bug and return only corrected Python code: def first(xs): return xs[1]",
                "```python\ndef first(xs):\n    return xs[0]\n```",
                "def first(xs):\n    return xs[0]",
            ),
            (
                "logic_puzzle",
                "Jo owns the dog. Sam does not own the bird. Who owns the cat?",
                "Sam owns the cat.",
                "Sam owns the cat.",
            ),
            (
                "code_generation",
                "Write a Python function named square(x) that returns x squared.",
                "```python\ndef square(x):\n    return x * x\n```",
                "def square(x):\n    return x * x",
            ),
        ]

        for category, prompt, candidate, expected in cases:
            with self.subTest(category=category):
                result = apply_answer_contract(TaskEnvelope(input_text=prompt), candidate)
                self.assertTrue(result.valid)
                self.assertEqual(result.answer, expected)

    def test_contract_mutation_grid_is_deterministic_and_ambiguity_safe(self) -> None:
        number_task = TaskEnvelope(input_text="Calculate the result. Return only the number.")
        number_cases = {
            "Answer: 0.": "0",
            "The result is -12.": "-12",
            "Final value: +1,250.50.": "1250.50",
            "Computed value: .75.": ".75",
            "Scientific notation: 1.2e-3.": "1.2e-3",
        }
        for candidate, expected in number_cases.items():
            with self.subTest(candidate=candidate):
                result = apply_answer_contract(number_task, candidate)
                self.assertTrue(result.valid)
                self.assertEqual(result.answer, expected)

        json_task = TaskEnvelope(input_text="Return only valid JSON containing the results.")
        payloads = [
            '["Ana","Maya"]',
            '[{"name":"Ana"},{"name":"Maya"}]',
            '{"answer":4}',
        ]
        wrappers = ["{}", "```json\n{}\n```", "Result:\n{}"]
        for payload in payloads:
            for wrapper in wrappers:
                with self.subTest(payload=payload, wrapper=wrapper):
                    result = apply_answer_contract(json_task, wrapper.format(payload))
                    self.assertTrue(result.valid)
                    self.assertEqual(json.loads(result.answer), json.loads(payload))

        ambiguous_inputs = [
            (number_task, "Choose 12 or 13."),
            (json_task, '{"a":1} or {"a":2}'),
        ]
        for task, candidate in ambiguous_inputs:
            with self.subTest(ambiguous=candidate):
                result = apply_answer_contract(task, candidate)
                self.assertFalse(result.valid)
                self.assertEqual(result.answer, candidate)

    def test_removes_preface_from_exact_bullet_contract(self) -> None:
        task = TaskEnvelope(input_text="Summarize the report in exactly three bullet points.")

        result = apply_answer_contract(task, "Here is the summary:\n- First.\n- Second.\n- Third.")

        self.assertTrue(result.valid)
        self.assertEqual(result.answer, "- First.\n- Second.\n- Third.")
        self.assertIn("removed_list_preface", result.actions)

    def test_recognizes_numeric_value_and_non_python_code_contracts(self) -> None:
        numeric = TaskEnvelope(input_text="Calculate the fee. Provide only the final numeric value.")
        signature = TaskEnvelope(input_text="Write only the Rust function signature for function get_user().")

        self.assertEqual(apply_answer_contract(numeric, "$312.50").answer, "312.50")
        code = apply_answer_contract(signature, "```rust\nfn get_user() -> User\n```")
        self.assertTrue(code.valid)
        self.assertEqual(code.answer, "fn get_user() -> User")

    def test_natural_exact_sentence_instruction_is_not_literal_echo(self) -> None:
        task = TaskEnvelope(
            input_text="Return exactly the single sentence containing the approved funding decision, with no commentary."
        )

        self.assertEqual(infer_expected_format(task), "free_text")
        self.assertEqual(infer_answer_contract(task).kind, AnswerContractKind.FREE_TEXT)

    def test_finalizer_normalizes_before_official_serialization(self) -> None:
        task = TaskEnvelope(id="t1", input_text="Classify sentiment. Answer exactly one label: positive, negative, or neutral.")
        raw = AnswerResult(id="t1", answer="The sentiment is negative.", route="e2b_local")

        final = finalize_answer_result(task, raw)

        self.assertEqual(final.answer, "negative")
        self.assertTrue(final.metadata["answer_contract"]["valid"])
        self.assertTrue(final.metadata["answer_contract"]["changed"])

    def test_finalizer_preserves_ambiguous_content(self) -> None:
        task = TaskEnvelope(id="t1", input_text="Answer exactly yes or no.")
        raw = AnswerResult(id="t1", answer="yes or no", route="fireworks_direct")

        final = finalize_answer_result(task, raw)

        self.assertEqual(final.answer, "yes or no")
        self.assertFalse(final.metadata["answer_contract"]["valid"])

    def test_rejects_negated_boolean_and_unsafe_python(self) -> None:
        boolean = apply_answer_contract(TaskEnvelope(input_text="Answer exactly yes or no."), "not yes")
        code = apply_answer_contract(
            TaskEnvelope(input_text="Write only Python code defining function run()."),
            "import os\ndef run():\n    return os.getcwd()",
        )
        self.assertFalse(boolean.valid)
        self.assertFalse(code.valid)
        self.assertEqual(code.reason, "unsafe_python_construct")

        fenced = apply_answer_contract(
            TaskEnvelope(input_text="Write only Python code defining function run()."),
            "```python\ndef run():\n    return 1\n```",
        )
        self.assertTrue(fenced.valid)
        self.assertEqual(fenced.answer, "def run():\n    return 1")


if __name__ == "__main__":
    unittest.main()
