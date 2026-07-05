import json
import tempfile
import unittest
from pathlib import Path

from router.evals.prompt_ablation import (
    analyze_prompt_manifest,
    write_prompt_ablation_report,
)


class PromptAblationTests(unittest.TestCase):
    def test_repository_prompt_manifest_is_valid(self) -> None:
        analysis = analyze_prompt_manifest(Path("prompts/manifest.json"))

        self.assertEqual(analysis["errors"], [])
        self.assertEqual(analysis["default_version"], "v1")
        self.assertEqual(len(analysis["versions"]["v1"]["prompts"]), 4)
        self.assertGreater(analysis["versions"]["v1"]["totals"]["approx_tokens"], 0)

    def test_missing_prompt_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "default_version": "v1",
                        "versions": {
                            "v1": {
                                "prompts": {
                                    "missing": "versions/v1/missing.txt",
                                }
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            analysis = analyze_prompt_manifest(manifest)

        self.assertEqual(len(analysis["errors"]), 1)
        self.assertIn("missing prompt file", analysis["errors"][0])

    def test_report_contains_risk_flags(self) -> None:
        analysis = analyze_prompt_manifest(Path("prompts/manifest.json"))
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "prompt-ablation.md"
            write_prompt_ablation_report(report, analysis)
            content = report.read_text(encoding="utf-8")

        self.assertIn("Prompt Ablation Report", content)
        self.assertIn("strict_json_output", content)


if __name__ == "__main__":
    unittest.main()
