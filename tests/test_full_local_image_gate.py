import unittest
from pathlib import Path

from scripts.full_local_image_gate import memory_to_mib


class FullLocalImageGateTests(unittest.TestCase):
    def test_championship_image_installs_litert_native_runtime_libraries(self) -> None:
        dockerfile = Path("Dockerfile.championship").read_text(encoding="utf-8")
        self.assertIn("libvulkan1", dockerfile)
        self.assertIn("mesa-vulkan-drivers", dockerfile)

    def test_memory_units(self) -> None:
        self.assertAlmostEqual(memory_to_mib("1024KiB"), 1.0)
        self.assertAlmostEqual(memory_to_mib("512MiB"), 512.0)
        self.assertAlmostEqual(memory_to_mib("2GiB"), 2048.0)

    def test_rejects_unknown_memory_unit(self) -> None:
        with self.assertRaises(ValueError):
            memory_to_mib("100 bytes")


if __name__ == "__main__":
    unittest.main()
