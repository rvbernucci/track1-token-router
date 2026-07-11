# Sprint 63 - Fireworks Pareto Threshold Calibration

## Objective

Use a bounded Fireworks budget to select the routing threshold and authorized remote model policy that maximize token savings without a measurable accuracy regression.

## Budget

- [x] Hard experiment cap: `US$10`.
- [x] Preferred first pass remained below `US$5`.
- [x] Estimated spend was only `US$0.00370335`, preserving the reserve.
- [x] Reconciled all `46` planned calls and their token usage.

## Candidates

- [x] Compare E2B thresholds `0.75`, `0.80` and `0.85` with grouped OOF evidence.
- [x] Compare always-Kimi and always-Minimax over the same 23 live tasks.
- [x] Compare a new per-intent Fireworks policy against both single-model baselines.
- [x] Keep prompt protocol, 96-token ceiling and task population identical.
- [x] Count invalid and failed-validator rows as not correct.

## Analysis

- [x] Compute accuracy, remote tokens, estimated cost and latency.
- [x] Compute paired accuracy regret against the strongest baseline.
- [x] Bootstrap token savings and report a 95% confidence interval.
- [x] Compute the Pareto frontier of accuracy versus scored Fireworks tokens.
- [x] Calculate regret under accuracy-first and token-first payoff scenarios.
- [x] Reject any Nash/Pareto candidate that violates the hard accuracy gate.

## Gates

- [x] No candidate exceeds the hard dollar cap.
- [x] Selected policy matches MiniMax accuracy at `21/23`.
- [x] Selected policy saves `1,902` tokens; bootstrap CI95 is `[1,608, 2,185]`.
- [x] E2B threshold `0.75` remains frozen from grouped OOF evaluation.
- [x] Every Fireworks call used the configured base URL and the two authorized candidates.

## Evidence

- `reports/generated/full-local/pareto-candidates.jsonl`
- `reports/generated/full-local/pareto-frontier.json`
- `reports/generated/full-local/fireworks-spend.json`
- `reports/public/final-pareto-calibration.md`

## Command

```bash
python3 scripts/calibrate_full_hybrid_frontier.py \
  --thresholds 0.75,0.80,0.85 \
  --budget-usd 10 --json
```

## Completion Decision

Passed. The nondominated intent policy keeps the strongest live accuracy while reducing tokens from `3,869` to `1,967`. Promote `configs/fireworks-intent-policy-v2.json` for final-image verification in Sprint 64.
