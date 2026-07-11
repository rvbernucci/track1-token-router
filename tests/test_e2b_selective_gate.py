import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from router.core.contracts import FeatureVector, TaskEnvelope
from router.orchestration.e2b_selective_gate import E2BSelectivePolicy, extract_e2b_response_signals


def _model(*, response: bool = False) -> dict[str, object]:
    names = ["bias", "intent.sentiment"]
    coefficients = [-1.0, 4.0]
    if response:
        names.append("response.canonical_sentiment")
        coefficients.append(4.0)
    return {"feature_names": names, "coefficients": coefficients}


def _write_policy(path: Path, *, enabled: bool = True) -> str:
    path.write_text(
        json.dumps(
            {
                "schema_version": "e2b-selective-policy-v1",
                "default_enabled": enabled,
                "thresholds": {"pre_probe": 0.5, "post_accept": 0.8},
                "models": {"pre_response": _model(), "post_response": _model(response=True)},
                "reason": "test policy",
            }
        ),
        encoding="utf-8",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


class E2BSelectiveGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.features = FeatureVector(
            names=("intent.sentiment", "score.reasoning_demand"),
            values=(1.0, 0.1),
        )

    def test_extracts_constraint_and_sentiment_signals(self) -> None:
        task = TaskEnvelope(id="x", input_text="Classify the sentiment. Return exactly 1 word: positive, negative, or neutral.")
        signals = extract_e2b_response_signals(task, "positive")
        values = dict(zip(signals.features.names, signals.features.values, strict=True))

        self.assertTrue(signals.mechanically_valid)
        self.assertEqual(values["response.canonical_sentiment"], 1.0)
        self.assertEqual(values["response.constraint_present"], 1.0)
        self.assertEqual(values["response.constraint_satisfied"], 1.0)

    def test_normalizes_unambiguous_verbose_sentiment(self) -> None:
        task = TaskEnvelope(id="x", input_text="Classify this sentiment as positive, negative, or neutral.")
        signals = extract_e2b_response_signals(task, "The sentiment is positive.")

        self.assertTrue(signals.mechanically_valid)
        self.assertEqual(signals.validated_answer, "positive")

    def test_policy_hash_is_pinned_and_disabled_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            digest = _write_policy(path, enabled=False)
            policy = E2BSelectivePolicy.load(path, expected_sha256=digest)

            decision = policy.should_probe(self.features)

        self.assertFalse(decision.probe)
        self.assertEqual(decision.reason, "selective_policy_disabled")

    def test_policy_accepts_only_valid_high_confidence_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            digest = _write_policy(path)
            policy = E2BSelectivePolicy.load(path, expected_sha256=digest)
            task = TaskEnvelope(id="x", input_text="Classify sentiment as positive, negative, or neutral.")

            accepted = policy.evaluate(task, "positive", self.features)
            rejected = policy.evaluate(task, "The sentiment could be positive or neutral.", self.features)

        self.assertTrue(accepted.accepted)
        self.assertEqual(accepted.answer, "positive")
        self.assertFalse(rejected.accepted)
        self.assertIn("mechanical_rejection", rejected.reason)

    def test_bad_hash_and_unknown_features_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            _write_policy(path)
            with self.assertRaises(ValueError):
                E2BSelectivePolicy.load(path, expected_sha256="0" * 64)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["models"]["pre_response"]["feature_names"] = ["bias", "unknown"]
            payload["models"]["pre_response"]["coefficients"] = [0.0, 1.0]
            path.write_text(json.dumps(payload), encoding="utf-8")
            policy = E2BSelectivePolicy.load(path)
            with self.assertRaises(ValueError):
                policy.should_probe(self.features)


if __name__ == "__main__":
    unittest.main()
