import unittest

from scripts.run_live_three_route_arena import _memory_mib, _route_class


class LiveThreeRouteArenaTests(unittest.TestCase):
    def test_route_classes(self):
        self.assertEqual(_route_class("solver_arithmetic"), "deterministic")
        self.assertEqual(_route_class("e2b_local"), "e2b")
        self.assertEqual(_route_class("fireworks_direct"), "fireworks")

    def test_memory_units(self):
        self.assertEqual(_memory_mib("1 GiB"), 1024)
        self.assertEqual(_memory_mib("512 MiB"), 512)


if __name__ == "__main__":
    unittest.main()
