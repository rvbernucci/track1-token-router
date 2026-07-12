import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("replay_router_ml_v3",ROOT/"scripts/replay_router_ml_v3.py")
MODULE=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)

class RouterMlV3RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.artifact={"feature_names":["x"],"normalization":{"mean":[0],"scale":[1]},"model":{"kind":"logistic","weights":[0,10]},"calibration":{"slope":1,"intercept":0},"thresholds":{"sentiment":{"threshold":.8}}}
    def test_selects_high_probability(self): self.assertEqual("e2b",MODULE.score({"x":1},"sentiment",self.artifact)["route"])
    def test_missing_feature_fails_closed(self): self.assertEqual("fireworks",MODULE.score({},"sentiment",self.artifact)["route"])
    def test_non_finite_fails_closed(self): self.assertEqual("fireworks",MODULE.score({"x":float("nan")},"sentiment",self.artifact)["route"])
    def test_unknown_intent_fails_closed(self): self.assertEqual("fireworks",MODULE.score({"x":1},"math_reasoning",self.artifact)["route"])

if __name__=="__main__":unittest.main()
