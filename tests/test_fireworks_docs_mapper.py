import unittest

from scripts.map_fireworks_docs import parse_index


class FireworksDocsMapperTests(unittest.TestCase):
    def test_parse_llms_index_rows(self) -> None:
        pages = parse_index(
            "\n".join(
                [
                    "# Fireworks AI Docs",
                    "- [Serverless Overview](https://docs.fireworks.ai/serverless/overview.md): How Serverless inference works",
                    "- [Deploying Fine Tuned Models](https://docs.fireworks.ai/fine-tuning/deploying-loras.md): Deploy LoRA models",
                    "- [Serverless Overview](https://docs.fireworks.ai/serverless/overview.md): duplicate ignored",
                ]
            )
        )

        self.assertEqual(len(pages), 2)
        self.assertEqual([page.path for page in pages], ["fine-tuning/deploying-loras.md", "serverless/overview.md"])
        self.assertEqual(pages[0].group, "fine-tuning")
        self.assertEqual(pages[1].priority, "critical")


if __name__ == "__main__":
    unittest.main()
