from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from router.orchestration.fireworks_intent_policy import FireworksIntentPolicy
from scripts.promote_fireworks_intent_policy import promote


KIMI = "accounts/fireworks/models/kimi-k2p7-code"
MINIMAX = "accounts/fireworks/models/minimax-m3"


class FireworksIntentPolicyTests(unittest.TestCase):
    def test_promotes_validation_choices_without_locked_test_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "comparison.json"
            path.write_text(json.dumps(_comparison()), encoding="utf-8")
            artifact = promote(path)

        self.assertEqual(artifact["default_model"], KIMI)
        self.assertEqual(artifact["intent_models"]["logic_puzzle"], MINIMAX)
        self.assertEqual(artifact["selection_split"], "validation")
        self.assertFalse(artifact["locked_test_used_for_selection"])
        self.assertTrue(artifact["default_enabled"])

    def test_loads_pinned_policy_and_maps_runtime_domain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            comparison = Path(tmp) / "comparison.json"
            comparison.write_text(json.dumps(_comparison()), encoding="utf-8")
            policy_path = Path(tmp) / "policy.json"
            policy_path.write_text(json.dumps(promote(comparison)), encoding="utf-8")
            digest = hashlib.sha256(policy_path.read_bytes()).hexdigest()

            policy = FireworksIntentPolicy.load(policy_path, expected_sha256=digest)
            selected = policy.select(domain="logic", runtime_allowed_models=[KIMI, MINIMAX])

        self.assertIsNotNone(selected)
        self.assertEqual(selected["intent"], "logic_puzzle")  # type: ignore[index]
        self.assertEqual(selected["model"], MINIMAX)  # type: ignore[index]
        self.assertFalse(selected["used_default"])  # type: ignore[index]

    def test_fails_closed_when_preferred_model_is_not_runtime_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            comparison = Path(tmp) / "comparison.json"
            comparison.write_text(json.dumps(_comparison()), encoding="utf-8")
            policy_path = Path(tmp) / "policy.json"
            policy_path.write_text(json.dumps(promote(comparison)), encoding="utf-8")
            policy = FireworksIntentPolicy.load(policy_path)

        selected = policy.select(domain="logic", runtime_allowed_models=[KIMI])
        self.assertEqual(selected["reason"], "preferred_model_not_runtime_allowed")  # type: ignore[index]
        self.assertNotIn("model", selected)  # type: ignore[operator]

    def test_failed_locked_test_gate_keeps_candidate_policy_disabled(self) -> None:
        comparison = _comparison()
        comparison["locked_test_policy"] = {"conservative_accuracy": 0.59}
        with tempfile.TemporaryDirectory() as tmp:
            comparison_path = Path(tmp) / "comparison.json"
            comparison_path.write_text(json.dumps(comparison), encoding="utf-8")
            policy_path = Path(tmp) / "policy.json"
            artifact = promote(comparison_path, accuracy_gate=0.60)
            policy_path.write_text(json.dumps(artifact), encoding="utf-8")
            policy = FireworksIntentPolicy.load(policy_path)

        self.assertFalse(artifact["default_enabled"])
        self.assertFalse(artifact["promotion_gate"]["passed"])
        selected = policy.select(domain="logic", runtime_allowed_models=[KIMI, MINIMAX])
        self.assertEqual(selected["reason"], "locked_test_promotion_gate_failed")  # type: ignore[index]
        self.assertNotIn("model", selected)  # type: ignore[operator]


def _comparison() -> dict[str, object]:
    choices = {
        "factual_qa": KIMI,
        "math_reasoning": KIMI,
        "sentiment": MINIMAX,
        "summarization": KIMI,
        "ner": KIMI,
        "code_debugging": KIMI,
        "logic_puzzle": MINIMAX,
        "code_generation": KIMI,
    }
    return {
        "schema_version": "fireworks-baseline-comparison-v1",
        "model_summary": {
            KIMI: {"validation": {"conservative_accuracy": 0.58, "average_tokens": 260}},
            MINIMAX: {"validation": {"conservative_accuracy": 0.56, "average_tokens": 357}},
        },
        "validation_selected_model_by_intent": choices,
        "locked_test_policy": {"conservative_accuracy": 0.99},
    }


if __name__ == "__main__":
    unittest.main()
