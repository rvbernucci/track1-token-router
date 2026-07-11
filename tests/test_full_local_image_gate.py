import unittest

from scripts.full_local_image_gate import memory_to_mib


class FullLocalImageGateTests(unittest.TestCase):
    def test_memory_units(self) -> None:
        self.assertAlmostEqual(memory_to_mib("1024KiB"), 1.0)
        self.assertAlmostEqual(memory_to_mib("512MiB"), 512.0)
        self.assertAlmostEqual(memory_to_mib("2GiB"), 2048.0)

    def test_rejects_unknown_memory_unit(self) -> None:
        with self.assertRaises(ValueError):
            memory_to_mib("100 bytes")


if __name__ == "__main__":
    unittest.main()
