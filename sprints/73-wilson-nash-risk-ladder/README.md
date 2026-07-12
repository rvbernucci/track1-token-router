# Sprint 73 - Wilson-Nash Risk Ladder

## Timebox

`60 minutes`. Freeze the payoff matrix and confidence thresholds before integration; no post-hoc tuning on the final holdout.

## Objective

Replace one binary E2B threshold with a monotonic four-tier decision ladder. Wilson quantifies cohort uncertainty; a deterministic minimax-regret selector decides whether token savings justify local-answer risk.

## Frozen Ladder

- [x] Use a `90%` Wilson confidence level for routing risk.
- [x] Distinguish confidence level from the lower-bound value in code, traces and documentation.
- [x] Route Wilson lower bound `>= 0.90` to E2B after Answer Contract checks.
- [x] Route bounds in `[0.80, 0.90)` to the Nash/minimax selector.
- [x] Reserve bounds in `[0.70, 0.80)` for one-call Fireworks `verify-or-repair` when Sprint 74 enables it.
- [x] Route bounds below `0.70` directly to Fireworks.
- [x] Retain Wilson `95%` in reports for conservative audit comparison.

## Game-Theoretic Model

- [x] Define actions: deterministic proof, E2B, verify-or-repair and direct Fireworks.
- [x] Model local and remote correctness intervals plus review feasibility and deadline failure.
- [x] Define accuracy reward first, tracked Fireworks tokens second and latency third.
- [x] Estimate local success from the promoted calibrated decision surface; rejected cluster features are excluded.
- [x] Store model-agnostic Fireworks probability and token envelopes by intent.
- [x] Compute utility intervals and worst-case regret for every feasible action.
- [x] Use deterministic tie-breaking toward the safer route.
- [x] Disable randomized mixed strategies.

## Safety Invariants

- [x] Deterministic proofs remain outside and before this E2B risk policy.
- [x] Invalid or unknown FunctionGemma output routes directly to Fireworks.
- [x] Increasing estimated risk cannot move a task to a less safe tier.
- [x] Decreasing support cannot improve the selected route; unit tests enforce monotonicity.
- [x] The policy chooses an action, never a model ID; `ALLOWED_MODELS` remains authoritative.
- [x] Deadline pressure disables review before it risks the ten-minute limit.

## Ablations

- [x] Compare Wilson 95 hard gate, Wilson 90 ladder and raw-probability aggressive policy.
- [x] Measure local coverage, false-local count and estimated Fireworks tokens.
- [x] Replay balanced, sentiment-heavy, code-heavy, math-heavy and deterministic random mixtures.
- [x] Reject the raw `0.70` policy: precision fell to `84.81%` for only `1,152` estimated saved tokens.

## Definition of Done

- [x] The ladder has a versioned, hash-pinned policy artifact, deterministic replay and unit-tested monotonicity.
- [x] Every decision exposes probability, Wilson bound, confidence level, support, utility, regret and reason without prompt contents.
