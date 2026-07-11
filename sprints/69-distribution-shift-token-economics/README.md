# Sprint 69 - Distribution Shift And Token Economics

## Objective

Measure accuracy, local coverage, latency and token savings when the hidden evaluator distribution differs sharply from the balanced development mix.

## Scenarios

- [ ] Balanced: equal weight across all eight categories.
- [ ] Sentiment/NER-heavy: at least 60% extraction and classification.
- [ ] Code-heavy: at least 60% debugging and generation.
- [ ] Math/logic-heavy: at least 60% reasoning tasks.
- [ ] Long-context-heavy: at least 50% prompts above the development p90 length.
- [ ] Fireworks-heavy: tasks designed to avoid deterministic and E2B release.
- [ ] Local-favorable: tasks inside measured deterministic/E2B cohorts.
- [ ] Seeded random mixtures from a Dirichlet category distribution.

## Execution

- [ ] Reweight only a frozen evaluation ledger; never regenerate answers per scenario.
- [ ] Preserve mutation lineages during bootstrap sampling.
- [ ] Evaluate current policy, always-Fireworks and local-disabled ablations.
- [ ] Simulate model unavailability and reordered `ALLOWED_MODELS`.
- [ ] Measure prompt, completion and total tokens separately.
- [ ] Measure time-budget exhaustion under worst-case remote latency.
- [ ] Run at least 1,000 seeded mixture simulations.

## Analysis

- [ ] Report accuracy, local precision, coverage and Fireworks tokens per scenario.
- [ ] Compute token savings and CI95 against always-Fireworks.
- [ ] Identify the break-even distribution where local routing stops saving tokens.
- [ ] Identify scenarios that exceed the 570-second runtime envelope.
- [ ] Compute worst-case regret for current and alternative policies.
- [ ] Produce sensitivity plots for threshold, category mix and remote latency.
- [ ] Separate observed metrics from projections in every report.

## Gates

- [ ] No scenario falls below the declared accuracy gate.
- [ ] Local precision remains at least `80%` in every scenario with 20+ local releases.
- [ ] Balanced, sentiment/NER-heavy and local-favorable scenarios save remote tokens.
- [ ] Worst-case runtime projection remains below `570 seconds` or triggers a documented safe policy.
- [ ] No authorization scenario produces an invalid model call.
- [ ] Every reported confidence interval uses lineage-aware resampling.
- [ ] Policy recommendation is frozen before final scenario comparison.

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

Keep one global policy only if it is robust across mixtures. Otherwise define a fail-closed runtime policy using input-only features, with no hidden-label adaptation or post-hoc threshold changes.
