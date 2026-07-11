# Sprint 69 - Distribution Shift And Token Economics

## Objective

Measure accuracy, local coverage, latency and token savings when the hidden evaluator distribution differs sharply from the balanced development mix.

## Scenarios

- [x] Balanced: equal weight across all eight categories.
- [x] Sentiment/NER-heavy: 70% extraction and classification.
- [x] Code-heavy: 70% debugging and generation.
- [x] Math/logic-heavy: 70% reasoning tasks.
- [x] Long-context-heavy: 50% prompts above frozen-ledger p90 length.
- [x] Fireworks-heavy: zero expected local releases.
- [x] Local-favorable: 100% deterministic/E2B cohort.
- [x] 1,000 seeded mixtures from a Dirichlet category distribution.

## Execution

- [x] Reweight only the 96-row ledger hash `775f6d5eba1996e2673d32e7dbcddbb6f788254f02bebda6edfe31b8e935ab36`.
- [x] Preserve mutation lineages during bootstrap sampling.
- [x] Evaluate current hybrid, always-Fireworks and local-disabled ablations.
- [x] Simulate reordered two-model lists and single-model unavailability.
- [x] Measure prompt, completion and total tokens separately.
- [x] Project time-budget exhaustion at 7,000 ms remote latency.
- [x] Run 1,000 seeded mixture simulations plus 1,000 lineage-aware replicates per fixed scenario.

## Analysis

- [x] Report accuracy, local precision, coverage and Fireworks tokens per scenario.
- [x] Compute lineage-aware token savings CI95 against always-Fireworks.
- [x] Establish that break-even lies outside the observed category simplex; minimum category saving is 348 tokens.
- [x] Identify five scenarios exceeding 570 seconds under the conservative 7-second projection.
- [x] Compute worst-case regret for current, always-Fireworks and local-disabled policies.
- [x] Produce sensitivity data for local release scale, category mixtures and remote latency.
- [x] Label observed ledger metrics and projected runtime/sensitivity separately.

## Gates

- [x] No scenario falls below the `60%` accuracy gate; random minimum was `86.46%`.
- [x] Local precision remains above `80%` in every qualifying scenario.
- [x] Balanced, sentiment/NER-heavy and local-favorable scenarios save tokens with positive CI95.
- [x] Runtime violations trigger a frozen 50-second reserve and non-zero fail-closed exit.
- [x] No authorization scenario selects outside `ALLOWED_MODELS`.
- [x] Every reported confidence interval uses lineage-aware resampling.
- [x] Policy candidates were frozen before scenario scoring.

## Evidence

- `evals/distribution-shift-v1/manifest.json`
- `configs/distribution-scenarios-v1.json`
- `reports/generated/distribution-shift-v1/simulations.jsonl`
- `reports/generated/distribution-shift-v1/break-even.json`
- `reports/public/distribution-shift-token-economics.md`

## Command

```bash
python3 scripts/run_distribution_shift_arena.py \
  --scenarios configs/distribution-scenarios-v1.json \
  --simulations 1000 --seed 69069 \
  --check --json
```

## Completion Decision

Status: **complete; retain hybrid with deadline guard**.

The hybrid remains above the accuracy gate and saves tokens in every fixed scenario and all 1,000 random mixtures. The lowest random accuracy was `86.46%`; the smallest random saving was 2,778 tokens. No feasible category mixture reaches token break-even. Under an intentionally pessimistic 7-second remote latency, five scenarios exceed 570 seconds, so the frozen recommendation keeps the current router but reserves the final 50 seconds and exits non-zero rather than emitting synthetic or incomplete success.
