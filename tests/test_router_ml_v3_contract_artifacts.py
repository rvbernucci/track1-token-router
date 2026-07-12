from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from scripts.replay_router_ml_v3 import score


ROOT = Path(__file__).resolve().parents[1]
FAST = ROOT / "evals/router-ml-v3/candidate-contract-v2-fast-rejected.json"
FULL = ROOT / "evals/router-ml-v3/candidate-contract-v2-full-rejected.json"


class ContractRouterArtifactsTests(unittest.TestCase):
    def test_rejected_candidates_are_hash_pinned_and_sentiment_only(self) -> None:
        expected = {
            FAST: "ffb24b764aef7f8cf3ce4a866f292635f71d1e8cfd849ce4776fa8eecbcb44d4",
            FULL: "b27e1887df3ebd3d7fe5b253c0f94694ed6417d15f45932674594276ff79eb3c",
        }
        for path, digest in expected.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            artifact = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["schema_version"], "router-ml-v3-runtime-v1")
            enabled = {
                intent
                for intent, threshold in artifact["thresholds"].items()
                if float(threshold["threshold"]) < 1.0
            }
            self.assertEqual(enabled, {"sentiment"})
            self.assertTrue(artifact["fail_closed"]["missing_assessment"])
            self.assertTrue(artifact["fail_closed"]["non_finite"])
            self.assertTrue(artifact["fail_closed"]["unknown_intent"])

    def test_missing_features_and_unknown_intents_fail_closed(self) -> None:
        artifact = json.loads(FAST.read_text(encoding="utf-8"))
        self.assertEqual(score({}, "sentiment", artifact)["route"], "fireworks")
        self.assertEqual(score({}, "unknown", artifact)["route"], "fireworks")


if __name__ == "__main__":
    unittest.main()
