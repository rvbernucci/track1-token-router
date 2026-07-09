import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ReleaseAutomationTests(unittest.TestCase):
    def test_release_workflow_is_tag_only_and_uses_github_token(self) -> None:
        content = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

        self.assertIn("tags:", content)
        self.assertIn('"v*"', content)
        self.assertIn('"offline-*"', content)
        self.assertIn("workflow_dispatch:", content)
        self.assertNotIn("branches:", content)
        self.assertIn("packages: write", content)
        self.assertIn("ghcr.io/${{ github.repository }}", content)
        self.assertIn("secrets.GITHUB_TOKEN", content)
        self.assertIn("docker/setup-buildx-action@v3", content)
        self.assertIn("docker/build-push-action@v6", content)
        self.assertIn("platforms: linux/amd64", content)
        self.assertIn("push: true", content)
        self.assertIn("org.opencontainers.image.source", content)
        self.assertIn("org.opencontainers.image.revision", content)
        self.assertIn("org.opencontainers.image.version", content)
        self.assertNotIn("FIREWORKS_API_KEY", content)

    def test_release_notes_dry_run_writes_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "release-notes.md"
            subprocess.run(
                [
                    sys.executable,
                    "scripts/generate_release_notes.py",
                    "--tag",
                    "offline-dry-run",
                    "--output",
                    str(output),
                    "--max-commits",
                    "3",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            content = output.read_text(encoding="utf-8")

        self.assertIn("# Release offline-dry-run", content)
        self.assertIn("## Changes", content)


if __name__ == "__main__":
    unittest.main()
