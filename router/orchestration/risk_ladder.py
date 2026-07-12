from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


SAFETY_ORDER = {"e2b": 0, "verify_or_repair": 1, "fireworks": 2}


@dataclass(frozen=True)
class RiskCandidate:
    action: str
    feasible: bool
    probability_low: float
    probability_high: float
    utility_low: float
    utility_high: float
    worst_case_regret: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class RiskLadderDecision:
    action: str
    tier: str
    reason: str
    probability: float
    wilson_lower: float
    confidence_level: float
    support: int
    candidates: tuple[RiskCandidate, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "tier": self.tier,
            "reason": self.reason,
            "probability": self.probability,
            "wilson_lower": self.wilson_lower,
            "confidence_level": self.confidence_level,
            "support": self.support,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


@dataclass(frozen=True)
class RiskLadderPolicy:
    enabled: bool
    confidence_level: float
    direct_local_lower: float
    nash_lower: float
    review_lower: float
    accuracy_reward: float
    token_penalty: float
    latency_penalty: float
    review_enabled: bool
    review_min_remaining_ms: int
    evidence_by_intent: Mapping[str, tuple[int, int]]
    remote_probability_by_intent: Mapping[str, float]
    remote_tokens_by_intent: Mapping[str, float]
    review_probability_by_intent: Mapping[str, float]
    review_tokens_by_intent: Mapping[str, float]
    eligibility_threshold_by_intent: Mapping[str, float]
    artifact_sha256: str

    @classmethod
    def load(cls, path: Path, *, expected_sha256: str | None = None) -> "RiskLadderPolicy":
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if expected_sha256 and digest != expected_sha256:
            raise ValueError("Risk ladder policy SHA-256 mismatch.")
        payload = json.loads(raw)
        if payload.get("schema_version") != "wilson-nash-risk-ladder-v1":
            raise ValueError("Risk ladder policy schema is invalid.")
        thresholds = payload.get("thresholds")
        utility = payload.get("utility")
        if not isinstance(thresholds, Mapping) or not isinstance(utility, Mapping):
            raise ValueError("Risk ladder thresholds and utility are required.")
        confidence = float(payload["wilson_confidence_level"])
        direct, nash, review = (
            float(thresholds["direct_local_lower"]),
            float(thresholds["nash_lower"]),
            float(thresholds["review_lower"]),
        )
        if confidence != 0.90 or not 0 <= review <= nash <= direct <= 1:
            raise ValueError("Risk ladder confidence or threshold ordering is invalid.")
        evidence = {}
        for intent, value in payload.get("evidence_by_intent", {}).items():
            successes, support = int(value["successes"]), int(value["support"])
            if support < 1 or not 0 <= successes <= support:
                raise ValueError("Risk ladder evidence is invalid.")
            evidence[str(intent)] = (successes, support)
        estimates = payload.get("estimates_by_intent", {})
        eligibility = payload.get("eligibility_threshold_by_intent", {})
        return cls(
            enabled=payload.get("default_enabled") is True,
            confidence_level=confidence,
            direct_local_lower=direct,
            nash_lower=nash,
            review_lower=review,
            accuracy_reward=float(utility["accuracy_reward"]),
            token_penalty=float(utility["fireworks_token_penalty"]),
            latency_penalty=float(utility["latency_ms_penalty"]),
            review_enabled=payload.get("review_enabled") is True,
            review_min_remaining_ms=int(payload["review_min_remaining_ms"]),
            evidence_by_intent=evidence,
            remote_probability_by_intent={str(k): float(v["direct_probability"]) for k, v in estimates.items()},
            remote_tokens_by_intent={str(k): float(v["direct_tokens"]) for k, v in estimates.items()},
            review_probability_by_intent={str(k): float(v["review_probability"]) for k, v in estimates.items()},
            review_tokens_by_intent={str(k): float(v["review_tokens"]) for k, v in estimates.items()},
            eligibility_threshold_by_intent={str(k): float(v) for k, v in eligibility.items()},
            artifact_sha256=digest,
        )

    def decide(self, *, intent: str, probability: float, remaining_ms: int) -> RiskLadderDecision:
        if not self.enabled or intent not in self.evidence_by_intent or not math.isfinite(probability):
            return self._decision("fireworks", "remote", "risk_policy_disabled_or_unknown", probability, 0.0, 0)
        if probability < self.eligibility_threshold_by_intent.get(intent, 1.0):
            return self._decision("fireworks", "remote", "outside_evidence_decision_surface", probability, 0.0, 0)
        successes, support = self.evidence_by_intent[intent]
        lower = wilson_lower(successes, support, confidence=self.confidence_level)
        if lower >= self.direct_local_lower:
            return self._decision("e2b", "direct_local", "wilson_direct_local", probability, lower, support)
        if lower >= self.nash_lower:
            candidates = self._minimax(intent=intent, probability=probability, lower=lower, remaining_ms=remaining_ms)
            selected = min(
                (candidate for candidate in candidates if candidate.feasible),
                key=lambda candidate: (
                    candidate.worst_case_regret,
                    -SAFETY_ORDER[candidate.action],
                    -candidate.probability_low,
                ),
            )
            return self._decision(
                selected.action, "nash_minimax", "minimum_worst_case_regret",
                probability, lower, support, candidates,
            )
        if lower >= self.review_lower and self.review_enabled and remaining_ms >= self.review_min_remaining_ms:
            return self._decision("verify_or_repair", "review", "wilson_review_band", probability, lower, support)
        reason = "deadline_disables_review" if lower >= self.review_lower else "wilson_below_review_floor"
        return self._decision("fireworks", "remote", reason, probability, lower, support)

    def _minimax(self, *, intent: str, probability: float, lower: float, remaining_ms: int) -> tuple[RiskCandidate, ...]:
        direct_probability = self.remote_probability_by_intent.get(intent, 0.90)
        direct_tokens = self.remote_tokens_by_intent.get(intent, 128.0)
        review_probability = self.review_probability_by_intent.get(intent, direct_probability)
        review_tokens = self.review_tokens_by_intent.get(intent, direct_tokens)
        candidates = [
            self._candidate("e2b", lower, max(lower, probability), 0.0, 0.0, True),
            self._candidate(
                "verify_or_repair", max(lower, review_probability - 0.05), min(1.0, review_probability + 0.02),
                review_tokens, 900.0,
                self.review_enabled and remaining_ms >= self.review_min_remaining_ms,
            ),
            self._candidate(
                "fireworks", max(0.0, direct_probability - 0.05), min(1.0, direct_probability + 0.03),
                direct_tokens, 1200.0, True,
            ),
        ]
        feasible = [candidate for candidate in candidates if candidate.feasible]
        completed = []
        for candidate in candidates:
            regret = (
                max(0.0, max(other.utility_high - candidate.utility_low for other in feasible))
                if candidate.feasible else self.accuracy_reward * 10.0
            )
            completed.append(RiskCandidate(**{**candidate.__dict__, "worst_case_regret": regret}))
        return tuple(completed)

    def _candidate(
        self, action: str, probability_low: float, probability_high: float,
        tokens: float, latency_ms: float, feasible: bool,
    ) -> RiskCandidate:
        return RiskCandidate(
            action=action,
            feasible=feasible,
            probability_low=probability_low,
            probability_high=probability_high,
            utility_low=self.accuracy_reward * probability_low - self.token_penalty * tokens - self.latency_penalty * latency_ms,
            utility_high=self.accuracy_reward * probability_high - self.token_penalty * tokens - self.latency_penalty * latency_ms,
        )

    def _decision(
        self, action: str, tier: str, reason: str, probability: float,
        lower: float, support: int, candidates: tuple[RiskCandidate, ...] = (),
    ) -> RiskLadderDecision:
        return RiskLadderDecision(
            action, tier, reason, probability, lower, self.confidence_level, support, candidates,
        )


def wilson_lower(successes: int, support: int, *, confidence: float = 0.90) -> float:
    if support <= 0:
        return 0.0
    if not 0 <= successes <= support:
        raise ValueError("Wilson successes must be in [0, support].")
    z_by_confidence = {0.90: 1.6448536269514722, 0.95: 1.959963984540054}
    if confidence not in z_by_confidence:
        raise ValueError("Only frozen 90% and audit 95% Wilson confidence levels are supported.")
    z, proportion = z_by_confidence[confidence], successes / support
    denominator = 1 + z * z / support
    center = proportion + z * z / (2 * support)
    margin = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * support)) / support)
    return (center - margin) / denominator
