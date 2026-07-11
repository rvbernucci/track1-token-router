import unittest

from router.core.contracts import TaskEnvelope, TokenUsage
from router.core.e2b_runner import E2B_PROMPT_VERSION, GemmaE2BRunner
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
    def test_enforces_litert_completion_alias(self):
        client = Client()
        result = GemmaE2BRunner(client, max_tokens=96).run(TaskEnvelope(id="task", input_text="Question"))
        self.assertEqual(client.request["max_tokens"], 96)
        self.assertEqual(client.request["extra_body"], {"max_completion_tokens": 96})
        self.assertEqual(client.request["messages"], [{"role": "user", "content": "Question"}])
        self.assertEqual(result.route, "e2b_local")
        self.assertEqual(result.metadata["prompt_version"], "raw-prompt-v1")


if __name__ == "__main__":
    unittest.main()
