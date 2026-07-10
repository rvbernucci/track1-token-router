import json
import tempfile
import unittest
from pathlib import Path

from scripts.merge_outcome_model_artifacts import merge_artifacts


def artifact(path: Path, models: dict) -> None:
    path.write_text(json.dumps({
        "schema_version": "engine-outcome-models-v1",
        "matrix_sha256": "a" * 64,
        "models": models,
    }))


class MergeOutcomeModelArtifactsTests(unittest.TestCase):
    def test_overrides_only_requested_model_and_preserves_remote(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact(root / "base.json", {"remote": {"version": 1}, "gemma4-e2b": {"version": 1}})
            artifact(root / "override.json", {"gemma4-e2b": {"version": 2}})
            report = merge_artifacts(
                base_path=root / "base.json",
                override_path=root / "override.json",
                model_ids=["gemma4-e2b"],
                output_path=root / "merged.json",
            )
            payload = json.loads((root / "merged.json").read_text())
            self.assertEqual(payload["models"]["remote"]["version"], 1)
            self.assertEqual(payload["models"]["gemma4-e2b"]["version"], 2)
            self.assertEqual(report["overridden_models"], ["gemma4-e2b"])

    def test_rejects_missing_override_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact(root / "base.json", {"remote": {}})
            artifact(root / "override.json", {"other": {}})
            with self.assertRaisesRegex(ValueError, "missing models"):
                merge_artifacts(
                    base_path=root / "base.json",
                    override_path=root / "override.json",
                    model_ids=["gemma4-e2b"],
                    output_path=root / "merged.json",
                )


if __name__ == "__main__":
    unittest.main()
