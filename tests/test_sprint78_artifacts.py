import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Sprint78ArtifactTests(unittest.TestCase):
    def test_policy_is_disabled_and_evidence_is_hash_pinned(self):
        policy = json.loads((ROOT / "configs/e2b-tool-policy-v1.json").read_text())
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["promoted_tools"], [])
        paths = {
            "corpus_sha256": "evals/tool-planner-v2/corpus.jsonl",
            "cuda_sealed_sha256": "reports/generated/e2b-tool-v2-cuda-sealed.json",
            "litert_parity_sha256": "reports/generated/e2b-tool-v2-litert-parity.json",
            "executor_audit_sha256": "reports/generated/e2b-tool-executor-audit.json",
            "runtime_parity_sha256": "reports/generated/e2b-tool-planner-cuda-parity.json",
        }
        for key, relative in paths.items():
            with self.subTest(key=key):
                digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
                self.assertEqual(policy["evidence"][key], digest)

    def test_corpus_is_complete_unique_and_lineage_sealed(self):
        rows = [json.loads(line) for line in (ROOT / "evals/tool-planner-v2/corpus.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), 500)
        self.assertEqual(len({row["id"] for row in rows}), 500)
        self.assertEqual(len({row["lineage"] for row in rows}), 500)
        self.assertEqual(sum(row["split"] == "sealed" for row in rows), 100)
        for family in ("inventory", "recipe", "calculator", "logic", "none"):
            self.assertEqual(sum(row["family"] == family for row in rows), 100)

    def test_executor_and_safety_audits_pass(self):
        audit = json.loads((ROOT / "reports/generated/e2b-tool-executor-audit.json").read_text())["summary"]
        self.assertEqual(audit["tasks"], 500)
        self.assertEqual(audit["passed"], 500)
        self.assertEqual(audit["unsupported_accepted"], 0)
        sealed = json.loads((ROOT / "reports/generated/e2b-tool-v2-cuda-sealed.json").read_text())["summary"]
        self.assertEqual(sealed["unsafe_false_positive"], 0)

    def test_failed_parity_gate_forces_retain(self):
        parity = json.loads((ROOT / "reports/generated/e2b-tool-planner-cuda-parity.json").read_text())
        self.assertLess(parity["release_agreement"], parity["common_tasks"])
        exact = json.loads((ROOT / "reports/generated/e2b-tool-exact-image-decision.json").read_text())
        self.assertEqual(exact["decision"], "retain")
        self.assertFalse(exact["experimental_policy_enabled"])


if __name__ == "__main__":
    unittest.main()
