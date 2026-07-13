import subprocess
import unittest
from pathlib import Path

from scripts.full_local_image_gate import memory_to_mib


class FullLocalImageGateTests(unittest.TestCase):
    def test_championship_image_installs_litert_native_runtime_libraries(self) -> None:
        dockerfile = Path("Dockerfile.championship").read_text(encoding="utf-8")
        self.assertIn("libvulkan1", dockerfile)
        self.assertIn("mesa-vulkan-drivers", dockerfile)

    def test_championship_entrypoint_is_posix_shell_and_uses_writable_runtime_paths(self) -> None:
        entrypoint = Path("scripts/championship_entrypoint.sh")
        subprocess.run(["sh", "-n", str(entrypoint)], check=True)
        content = entrypoint.read_text(encoding="utf-8")
        dockerfile = Path("Dockerfile.championship").read_text(encoding="utf-8")
        self.assertIn("/tmp/proofroute", content)
        self.assertIn("ROUTER_LOG_PATH=/tmp/proofroute/run.jsonl", dockerfile)
        self.assertNotIn(">/app/logs/", content)

    def test_championship_entrypoint_falls_back_to_remote_instead_of_crashing(self) -> None:
        content = Path("scripts/championship_entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn("export ROUTER_MODE=fireworks", content)
        self.assertIn('remote_only "FunctionGemma startup failure"', content)
        self.assertIn('remote_only "FunctionGemma planner startup failure"', content)
        self.assertIn('remote_only "Gemma E2B startup failure"', content)
        self.assertIn("exec router submit-track1", content)

    def test_challenger_embeds_hash_pinned_independent_planner(self) -> None:
        dockerfile = Path("Dockerfile.championship").read_text(encoding="utf-8")
        entrypoint = Path("scripts/championship_entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn("functiongemma-tool-planner-q8_0.gguf", dockerfile)
        self.assertIn("ec412795782acd3ed836ac35e058099bfdb1c3218a1ee86aef32905377dbddaf", dockerfile)
        self.assertIn("dual-functiongemma-policy-v1-promoted.json", dockerfile)
        self.assertIn("DUAL_FUNCTIONGEMMA_POLICY_SHA256=611dfac1494674e0a423ddda1ddc06ca01d3671afb2660519b5e97a328d97ff4", dockerfile)
        self.assertIn("--port 8092", entrypoint)
        self.assertIn("planner_pid", entrypoint)

    def test_harness_compatibility_gate_covers_hostile_runtime_conditions(self) -> None:
        content = Path("scripts/harness_compat_gate.sh").read_text(encoding="utf-8")
        self.assertIn("--read-only --user 65534:65534", content)
        self.assertIn("PROOFROUTE_DISABLE_LOCAL=1", content)
        self.assertIn("Official Fireworks runtime requires harness variables", content)
        self.assertIn("--network=none", content)

    def test_memory_units(self) -> None:
        self.assertAlmostEqual(memory_to_mib("1024KiB"), 1.0)
        self.assertAlmostEqual(memory_to_mib("512MiB"), 512.0)
        self.assertAlmostEqual(memory_to_mib("2GiB"), 2048.0)

    def test_rejects_unknown_memory_unit(self) -> None:
        with self.assertRaises(ValueError):
            memory_to_mib("100 bytes")


if __name__ == "__main__":
    unittest.main()
