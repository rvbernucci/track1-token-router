import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Sprint79ArtifactTests(unittest.TestCase):
    def test_dual_policy_stays_disabled_until_planner_exists(self):
        policy = json.loads((ROOT / "configs/dual-functiongemma-policy-v1.json").read_text())
        self.assertFalse(policy["enabled"])
        self.assertIsNone(policy["planner"]["sha256"])
        self.assertEqual(policy["assessment"]["format"], "GGUF")
        self.assertEqual(policy["e2b"]["format"], "LiteRT-LM")

    def test_capacity_gate_passes_under_resource_envelope(self):
        report = json.loads((ROOT / "reports/generated/dual-functiongemma-resource-gate.json").read_text())
        self.assertTrue(report["passed"])
        self.assertLessEqual(report["measurements"]["peak_sampled_memory_mib"], 3686.4)
        self.assertLessEqual(report["measurements"]["cold_start_seconds"], 30)
        self.assertEqual(report["measurements"]["failures"], 0)
        self.assertFalse(report["measurements"]["oom_killed"])

    def test_corpus_manifest_hashes_and_audit(self):
        root = ROOT / "data/functiongemma-tool-planner-v1"
        manifest = json.loads((root / "manifest.json").read_text())
        self.assertEqual(manifest["rows"], 2500)
        self.assertEqual(manifest["unique_lineages"], 2500)
        self.assertGreaterEqual(manifest["outside_training_fraction"], 0.2)
        for split, expected in manifest["sha256"].items():
            digest = hashlib.sha256((root / f"{split}.jsonl").read_bytes()).hexdigest()
            self.assertEqual(digest, expected)
        audit = json.loads((ROOT / "reports/generated/functiongemma-tool-corpus-audit.json").read_text())
        self.assertTrue(audit["passed"])
        self.assertEqual(audit["summary"]["errors"], 0)
        self.assertFalse(any(audit["summary"]["split_overlaps"].values()))


if __name__ == "__main__":
    unittest.main()
