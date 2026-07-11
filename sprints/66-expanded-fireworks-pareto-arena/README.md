# Sprint 66 - Expanded Fireworks Pareto Arena

## Objective

Expand the paired Kimi/MiniMax evidence from 23 to 160-240 unseen tasks while preserving identical prompts, token ceilings and validators.

## Dataset

- [ ] Build 192 tasks, 24 per Track 1 category.
- [ ] Balance easy, medium and hard tasks within every category.
- [ ] Include at least 96 mechanically scorable tasks.
- [ ] Freeze prompt hashes, validators and output ceilings before API calls.
- [ ] Exclude all current 23-task microbench rows and normalized duplicates.
- [ ] Keep hidden test labels inaccessible to the model-selection code.

## Execution

- [ ] Call both `minimax-m3` and `kimi-k2p7-code` for every task.
- [ ] Use the same raw-prompt protocol, temperature and task-specific token ceiling.
- [ ] Route every request through configured `FIREWORKS_BASE_URL`.
- [ ] Verify both model IDs against runtime `ALLOWED_MODELS` before each run.
- [ ] Set a hard experiment budget of `US$5` and stop on unreconciled usage.
- [ ] Persist prompt, completion and total tokens separately.
- [ ] Preserve latency, validation reason, HTTP failure and retry metadata.

## Analysis

- [ ] Compute paired accuracy by model, category, difficulty and output shape.
- [ ] Compute prompt, completion and total token distributions.
- [ ] Bootstrap paired accuracy deltas and token savings by mutation lineage.
- [ ] Build accuracy-versus-token Pareto frontiers with confidence intervals.
- [ ] Compare always-Kimi, always-MiniMax, current intent policy and learned alternatives.
- [ ] Calculate minimax regret and Nash equilibrium under accuracy-first constraints.
- [ ] Penalize invalid, timeout and judge-disagreement rows as incorrect.

## Gates

- [ ] At least 180 complete paired rows.
- [ ] Zero calls outside `FIREWORKS_BASE_URL` and `ALLOWED_MODELS`.
- [ ] Total estimated spend does not exceed `US$5`.
- [ ] Selected policy has no paired accuracy regression above one percentage point.
- [ ] Selected policy has positive token savings with CI95 lower bound above zero.
- [ ] Every selected category-model preference has at least 20 observations.
- [ ] Policy is frozen before the sealed test split is scored.

## Evidence

- `evals/fireworks-pareto-v2/manifest.json`
- `evals/fireworks-pareto-v2/sealed/tasks.jsonl`
- `reports/generated/fireworks-pareto-v2/paired-results.jsonl`
- `reports/generated/fireworks-pareto-v2/frontier.json`
- `reports/public/fireworks-pareto-v2.md`

## Command

```bash
python3 scripts/run_fireworks_pareto_v2.py \
  --models minimax-m3,kimi-k2p7-code \
  --budget-usd 5 \
  --check --json
```

## Completion Decision

Promote only a nondominated, accuracy-equivalent policy. Retain `fireworks-intent-policy-v2.json` when the expanded evidence does not justify a change.
