import unittest

from scripts.three_route_container_drill import _markdown


class ThreeRouteContainerDrillTests(unittest.TestCase):
    def test_markdown_records_pass_and_all_checks(self) -> None:
        report = _markdown(
            {
                "passed": True,
                "image": "example/image:tag",
                "checks": {"local": True, "remote": True},
            }
        )

        self.assertIn("Decision: `PASS`", report)
        self.assertIn("- [x] `local`", report)
        self.assertIn("example/image:tag", report)


if __name__ == "__main__":
    unittest.main()
