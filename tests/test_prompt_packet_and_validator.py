import unittest

from router.core.contracts import TaskEnvelope
from router.orchestration.final_validator import (
    repair_final_answer,
    validate_final_answer,
    validate_or_safely_repair_final_answer,
)
from router.orchestration.prompt_packet import (
    build_remote_audit_packet,
    estimate_policy_packet_tokens,
    extract_literal_echo,
    infer_expected_format,
)


class PromptPacketTests(unittest.TestCase):
    def test_packet_is_compact_and_has_expected_format(self) -> None:
        task = TaskEnvelope(input_text="Return only compact JSON with key answer set to 4.")

        packet = build_remote_audit_packet(task, candidate='{"answer":4}', concern="format risk")

        self.assertEqual(packet.expected_format, "json")
        self.assertLess(packet.approx_tokens(), 80)
        self.assertIn("EXPECTED_FORMAT:json", packet.render())

    def test_policy_packet_estimate_counts_only_remote_routes(self) -> None:
        tasks = [
            TaskEnvelope(input_text="What is 2 + 2?", metadata={"category": "facil"}),
            TaskEnvelope(input_text="What is the latest GPU cloud price?", metadata={"category": "conhecimento_instavel"}),
        ]

        tokens = estimate_policy_packet_tokens(tasks, "balanced")

        self.assertGreater(tokens, 0)


class FinalValidatorTests(unittest.TestCase):
    def test_validates_json_answer(self) -> None:
        task = TaskEnvelope(input_text="Return only JSON with key answer.")

        result = validate_final_answer(task, '{"answer":4}')

        self.assertTrue(result.valid)
        self.assertEqual(result.expected_format, "json")

    def test_repairs_json_wrapped_in_markdown(self) -> None:
        task = TaskEnvelope(input_text="Return only JSON with key answer.")

        result = validate_final_answer(task, '```json\n{"answer":4}\n```')

        self.assertFalse(result.valid)
        self.assertEqual(result.repaired_answer, '{"answer":4}')

    def test_safely_releases_repaired_json(self) -> None:
        task = TaskEnvelope(input_text="Return only JSON with key answer.")

        result = validate_or_safely_repair_final_answer(task, '```json\n{"answer":4}\n```')

        self.assertTrue(result.valid)
        self.assertEqual(result.reason, "safe_repair:markdown_fence_in_strict_format")
        self.assertEqual(result.repaired_answer, '{"answer":4}')

    def test_does_not_extract_first_number_from_fenced_explanation(self) -> None:
        task = TaskEnvelope(input_text="What is 12 - 5? Return only the number.")

        result = validate_or_safely_repair_final_answer(
            task,
            "```text\n12 minus 5 equals 7\n```",
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "markdown_fence_in_strict_format")

    def test_repairs_python_code_wrapped_in_markdown(self) -> None:
        task = TaskEnvelope(input_text="Return only Python code. Define a function add(a, b).")

        result = validate_final_answer(task, "```python\ndef add(a, b):\n    return a + b\n```")

        self.assertFalse(result.valid)
        self.assertEqual(result.expected_format, "code")
        self.assertEqual(result.repaired_answer, "def add(a, b):\n    return a + b")

    def test_repairs_python_code_with_leading_reasoning(self) -> None:
        task = TaskEnvelope(
            input_text=(
                "Write a Python function unique_preserve_order(items) that removes duplicates "
                "while preserving first occurrence order."
            )
        )
        answer = (
            "The user wants a Python function. I should return only code.\n\n"
            "def unique_preserve_order(items):\n"
            "    seen = set()\n"
            "    result = []\n"
            "    for item in items:\n"
            "        if item not in seen:\n"
            "            seen.add(item)\n"
            "            result.append(item)\n"
            "    return result"
        )

        result = validate_final_answer(task, answer)

        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "python_code_with_extra_text")
        self.assertTrue(result.repaired_answer.startswith("def unique_preserve_order(items):"))
        self.assertNotIn("The user wants", result.repaired_answer)

    def test_rejects_unparseable_python_code(self) -> None:
        task = TaskEnvelope(input_text="Return only Python code. Define a function add(a, b).")

        result = validate_final_answer(task, "def add(a, b):")

        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "invalid_python_code")

    def test_infers_natural_python_function_request_as_code(self) -> None:
        task = TaskEnvelope(input_text="Write a Python function add(a, b) that returns the sum.")

        self.assertEqual(infer_expected_format(task), "code")

    def test_validates_number_only_answer(self) -> None:
        task = TaskEnvelope(input_text="What is 12 - 5? Return only the number.")

        result = validate_final_answer(task, "7")

        self.assertTrue(result.valid)

    def test_repairs_number_with_extra_text(self) -> None:
        task = TaskEnvelope(input_text="What is 12 - 5? Return only the number.")

        result = repair_final_answer(task, "The answer is 7.")

        self.assertEqual(result.repaired_answer, "7")

    def test_validates_literal_echo(self) -> None:
        task = TaskEnvelope(input_text="Return exactly SAFE_OUTPUT and nothing else.")

        result = validate_final_answer(task, "SAFE_OUTPUT")

        self.assertTrue(result.valid)
        self.assertEqual(infer_expected_format(task), "literal_echo")

    def test_validates_literal_echo_this_string_colon(self) -> None:
        task = TaskEnvelope(input_text="Return exactly this string and nothing else: ROUTER-OK-19")

        result = validate_final_answer(task, "ROUTER-OK-19")

        self.assertTrue(result.valid)
        self.assertEqual(extract_literal_echo(task), "ROUTER-OK-19")
        self.assertEqual(infer_expected_format(task), "literal_echo")

    def test_validates_yes_no_without_literal_echo_repair(self) -> None:
        task = TaskEnvelope(input_text="Is the door locked? Return exactly yes or no.")

        result = validate_final_answer(task, "yes")

        self.assertTrue(result.valid)
        self.assertEqual(infer_expected_format(task), "yes_no")

    def test_repairs_yes_no_when_single_label_is_present(self) -> None:
        task = TaskEnvelope(input_text="Is the door locked? Return exactly yes or no.")

        result = repair_final_answer(task, "Yes, the door is locked.")

        self.assertEqual(result.repaired_answer, "yes")

    def test_does_not_repair_ambiguous_yes_no(self) -> None:
        task = TaskEnvelope(input_text="Is the door locked? Return exactly yes or no.")

        result = repair_final_answer(task, "yes or no")

        self.assertEqual(result.repaired_answer, "")

    def test_free_text_allows_natural_answer(self) -> None:
        task = TaskEnvelope(input_text="Explain Nash equilibrium briefly.")

        result = validate_final_answer(task, "A stable strategy profile.")

        self.assertTrue(result.valid)

    def test_free_text_rejects_repeated_generation_loop(self) -> None:
        task = TaskEnvelope(input_text="Who is the president of Brazil?")
        answer = (
            "The president of Brazil is the elected head of state. "
            "president of Brazil and president of Brazil and president of Brazil and "
            "president of Brazil and president of Brazil"
        )

        result = validate_final_answer(task, answer)

        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "degenerate_repetition")

    def test_free_text_rejects_unclosed_markdown_fence(self) -> None:
        task = TaskEnvelope(input_text="Summarize this paragraph briefly.")

        result = validate_final_answer(task, "```text\nA summary that never closes")

        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "unclosed_markdown_fence")

    def test_free_text_does_not_reject_repeated_entities_in_a_list(self) -> None:
        task = TaskEnvelope(input_text="Extract all named entities from the text.")
        answer = "Ana; Ana; Bruno; Carla; Ana"

        result = validate_final_answer(task, answer)

        self.assertTrue(result.valid)


if __name__ == "__main__":
    unittest.main()
