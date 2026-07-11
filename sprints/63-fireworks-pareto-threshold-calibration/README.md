# Sprint 63 - Fireworks Pareto Threshold Calibration

## Objective

Use a bounded Fireworks budget to select the routing threshold and authorized remote model policy that maximize token savings without a measurable accuracy regression.

## Budget

- [ ] Hard experiment cap: `US$10`.
- [ ] Preferred first pass: `US$5`.
- [ ] Preserve at least `US$35` as submission and incident reserve.
- [ ] Stop immediately if cumulative usage or request count cannot be reconciled.

## Candidates

- [ ] Compare E2B thresholds `0.75`, `0.80` and `0.85`.
- [ ] Compare always-Kimi and always-Minimax baselines where both are authorized.
- [ ] Compare the existing per-intent Fireworks policy against the best single-model baseline.
- [ ] Keep prompt protocol, output ceilings and task population identical across candidates.
- [ ] Count invalid, timeout and judge-disagreement rows as not correct.

## Analysis

- [ ] Compute accuracy, remote tokens, cost, latency and local coverage.
- [ ] Compute paired accuracy deltas against the strongest baseline.
- [ ] Bootstrap token savings and report a 95% confidence interval.
- [ ] Plot the Pareto frontier of accuracy versus scored Fireworks tokens.
- [ ] Calculate regret under accuracy-first and token-first payoff scenarios.
- [ ] Reject any Nash/Pareto candidate that violates the hard accuracy gate.

## Gates

- [ ] No candidate exceeds the hard dollar cap.
- [ ] Selected policy has no material paired accuracy regression.
- [ ] Selected policy has positive token savings with a positive lower confidence bound.
- [ ] Threshold remains frozen after holdout evaluation begins.
- [ ] Every Fireworks call uses only `FIREWORKS_BASE_URL` and `ALLOWED_MODELS`.

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

Prefer the highest-accuracy nondominated policy. Use token count only to break accuracy-equivalent choices.
