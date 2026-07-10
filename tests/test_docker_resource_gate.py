from __future__ import annotations

from pathlib import Path
import subprocess
import unittest


class DockerResourceGateTests(unittest.TestCase):
    def test_gate_has_valid_shell_and_official_limits(self) -> None:
        path = Path("scripts/docker_resource_gate.sh")
        subprocess.run(["bash", "-n", str(path)], check=True)
        content = path.read_text(encoding="utf-8")

        self.assertIn("--memory=4g", content)
        self.assertIn("--cpus=2", content)
        self.assertIn("--network=none", content)
        self.assertIn("timeout 600", content)
        self.assertIn("linux/amd64", content)
        self.assertIn("10000000000", content)
        self.assertIn("results.json", content)
        self.assertIn("resource-usage.json", content)
        self.assertIn("process_max_rss_mib", content)

        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
        self.assertNotIn("COPY artifacts", dockerfile)
        self.assertNotIn("FUNCTIONGEMMA_ARTIFACT", dockerfile)
        self.assertNotIn("E2B_ARTIFACT", dockerfile)

    def test_ci_and_release_execute_the_resource_gate(self) -> None:
        ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
        release = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
        public_audit = Path(".github/workflows/public-image-audit.yml").read_text(encoding="utf-8")

        self.assertIn("scripts/docker_resource_gate.sh", ci)
        self.assertIn("scripts/docker_resource_gate.sh", release)
        self.assertGreaterEqual(release.count("scripts/docker_resource_gate.sh"), 2)
        self.assertIn("docker pull --platform linux/amd64", release)
        self.assertIn("scripts/docker_resource_gate.sh", public_audit)
        self.assertIn("docker pull --platform linux/amd64", public_audit)
        self.assertNotIn("docker/login-action", public_audit)


if __name__ == "__main__":
    unittest.main()
