import unittest

from scripts.run_full_local_arena import _wilson_lower


class FullLocalArenaTests(unittest.TestCase):
    def test_wilson_lower_is_conservative(self) -> None:
        self.assertGreater(_wilson_lower(40, 40), 0.90)
        self.assertLess(_wilson_lower(40, 40), 1.0)
        self.assertEqual(_wilson_lower(0, 0), 0.0)


if __name__ == "__main__":
    unittest.main()
