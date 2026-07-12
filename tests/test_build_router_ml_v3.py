import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("build_router_ml_v3",ROOT/"scripts/build_router_ml_v3_ledger.py")
MODULE=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)

class RouterMlV3LedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.rows,cls.manifest=MODULE.build(ROOT)
    def test_complete_4400_inventory(self): self.assertEqual(4400,len(self.rows)); self.assertEqual({"fit":2640,"calibration":880,"protected_holdout":880},self.manifest["roles"])
    def test_protected_targets_are_redacted(self): self.assertTrue(all(row["targets"]=={"deterministic":None,"e2b":None} for row in self.rows if row["role"]=="protected_holdout"))
    def test_lineages_are_disjoint(self): self.assertEqual({"fit_calibration":0,"fit_protected_holdout":0,"calibration_protected_holdout":0},self.manifest["lineage_overlap"])
    def test_no_forbidden_runtime_features(self):
        forbidden=("answer","correct","provider","judge","gold","reference")
        self.assertFalse([name for name in self.rows[0]["features"] if any(item in name for item in forbidden)])

if __name__=="__main__":unittest.main()
