import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "fit_router_ml_v3", ROOT / "scripts" / "fit_router_ml_v3.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RouterMlV3ThresholdTests(unittest.TestCase):
    def test_keeps_small_high_confidence_cohort(self):
        rows = [
            {"intent": "sentiment", "targets": {"e2b": 1}}
            for _ in range(17)
        ] + [{"intent": "sentiment", "targets": {"e2b": 0}}]
        probabilities = [0.99 - index * 0.001 for index in range(17)] + [0.90]

        selected = MODULE._thresholds(rows, probabilities)["sentiment"]

        self.assertEqual(17, selected["selected"])
        self.assertEqual(17, selected["correct"])
        self.assertGreater(selected["wilson_lower_90"], 0.85)


if __name__ == "__main__":
    unittest.main()
