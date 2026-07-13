import unittest

from router.core.contracts import TaskEnvelope, TokenUsage
from router.core.e2b_runner import E2B_PROMPT_VERSION, E2B_SYSTEM_PROMPT, GemmaE2BRunner
from router.core.model_client import ModelResponse


class Client:
    model = "gemma4-e2b"

    def complete(self, messages, *, temperature, max_tokens, extra_body=None):
        self.request = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "extra_body": extra_body,
        }
        return ModelResponse(text="answer", usage=TokenUsage(prompt=0, completion=0, total=0))


class E2BRunnerTests(unittest.TestCase):
    def test_prompt_requires_english_natural_language(self):
        self.assertIn("Use English for all natural-language text", E2B_SYSTEM_PROMPT)

    def test_enforces_litert_completion_alias(self):
        client = Client()
        result = GemmaE2BRunner(client, max_tokens=96).run(TaskEnvelope(id="task", input_text="Question"))
        self.assertEqual(client.request["max_tokens"], 96)
        self.assertEqual(client.request["extra_body"], {"max_completion_tokens": 96})
        self.assertEqual(
            client.request["messages"],
            [
                {"role": "system", "content": E2B_SYSTEM_PROMPT},
                {"role": "user", "content": "Question"},
            ],
        )
        self.assertEqual(result.route, "e2b_local")
        self.assertEqual(result.metadata["prompt_version"], "generic-answer-contract-v2-english")

    def test_retry_doubles_only_the_completion_ceiling(self):
        client = Client()
        result = GemmaE2BRunner(client, max_tokens=96).retry(TaskEnvelope(id="task", input_text="Question"))

        self.assertEqual(client.request["max_tokens"], 192)
        self.assertEqual(client.request["extra_body"], {"max_completion_tokens": 192})
        self.assertEqual(result.route, "e2b_local_retry")
        self.assertTrue(result.metadata["contract_retry"])


if __name__ == "__main__":
    unittest.main()
