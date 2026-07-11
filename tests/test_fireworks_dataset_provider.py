import unittest

from router.dataset_forge.providers import FireworksDatasetProvider, ProviderError, _parse_json_object
from tests.fake_openai_server import FakeOpenAIServer


class FireworksDatasetProviderTests(unittest.TestCase):
    def test_structured_parser_preserves_first_complete_object_with_trailing_output(self) -> None:
        self.assertEqual(_parse_json_object('{"items": []}\n{"duplicate": true}', "test"), {"items": []})

    def test_structured_parser_rejects_malformed_first_object(self) -> None:
        with self.assertRaises(ProviderError):
            _parse_json_object('prefix {"items": []}', "test")

    def test_minimax_judge_uses_proven_reasoning_option(self):
        with FakeOpenAIServer(response_text='{"judgments": []}') as server:
            provider = FireworksDatasetProvider(
                api_key="test-key",
                base_url=server.url,
                model="accounts/fireworks/models/minimax-m3",
                max_tokens=32,
            )

            provider.invoke(
                prompt="Judge an empty batch.",
                response_schema={"type": "object"},
                role="outcome_judge",
            )

        body = server.requests[0]["payload"]
        self.assertEqual(body["reasoning_effort"], "none")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["user"], "dataset-forge-v1")

    def test_gemma_does_not_receive_unsupported_reasoning_option(self):
        with FakeOpenAIServer(response_text='{"items": []}') as server:
            provider = FireworksDatasetProvider(
                api_key="test-key",
                base_url=server.url,
                model="accounts/fireworks/models/gemma-4-31b-it",
                max_tokens=32,
            )

            provider.invoke(
                prompt="Generate an empty batch.",
                response_schema={"type": "object"},
                role="generator",
            )

        self.assertNotIn("reasoning_effort", server.requests[0]["payload"])


if __name__ == "__main__":
    unittest.main()
