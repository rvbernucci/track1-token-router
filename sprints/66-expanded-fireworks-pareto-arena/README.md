# Sprint 66 - Expanded Fireworks Pareto Arena

## Objective

Expand the paired Kimi/MiniMax evidence from 23 to 160-240 unseen tasks while preserving identical prompts, token ceilings and validators.

## Dataset

- [x] Build 192 tasks, 24 per Track 1 category.
- [x] Balance easy, medium and hard tasks: 64 rows each.
- [x] Make all 192 tasks mechanically scorable.
- [x] Freeze prompt hashes, validators and task-specific output ceilings before API calls.
- [x] Verify zero normalized duplicates against 133 prior Pareto prompts.
- [x] Select on 160 development rows and score the frozen policy on 32 sealed rows.

## Execution

- [x] Call both `minimax-m3` and `kimi-k2p7-code` for every task: 384 successful calls.
- [x] Use the same raw-prompt protocol, temperature zero and task-specific token ceiling.
- [x] Route every request through configured `FIREWORKS_BASE_URL`.
- [x] Verify both model IDs against runtime `ALLOWED_MODELS` before every call.
- [x] Enforce a hard `US$5` budget; actual estimated spend was `US$0.0312178`.
- [x] Persist prompt, completion and total tokens separately.
- [x] Preserve latency, validation reason, request options, failures and fallback metadata.

## Analysis

- [x] Compute paired accuracy by model, category, difficulty and output shape.
- [x] Compute prompt, completion and total token measurements.
- [x] Bootstrap paired accuracy deltas and changed-route token savings by mutation lineage.
- [x] Build accuracy-versus-token Pareto evidence with confidence intervals.
- [x] Compare always-Kimi, always-MiniMax, current intent policy and frozen development policy.
- [x] Calculate minimax regret and an accuracy-first mixed Nash strategy.
- [x] Penalize invalid and failed rows as incorrect; all labels were mechanical.

## Gates

- [x] 192 complete paired rows.
- [x] Zero calls outside `FIREWORKS_BASE_URL` and `ALLOWED_MODELS`.
- [x] Total estimated spend `US$0.0312178`, below `US$5`.
- [x] Selected policy improves sealed accuracy from `84.38%` to `96.88%`.
- [x] Changed-route token savings CI95 is `87` to `87` tokens per NER row.
- [x] Every selected category-model preference has 20 development observations.
- [x] Policy was frozen before the sealed split was scored.

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

Status: **complete and promoted**.

Always-Kimi dominates the deployed intent policy on the sealed split: accuracy rises from `84.38%` to `96.88%`, while the only changed route (`NER`) saves 87 tokens per row. Across all 192 paired tasks, Kimi scored `96.35%` using 14,441 tokens; MiniMax scored `83.85%` using 32,558 tokens. The development-only alternative that sends debugging to MiniMax reached `100%` on 32 sealed rows but spent more tokens, so it remains an unpromoted Pareto point. `configs/fireworks-intent-policy-v2.json` now routes every intent to Kimi. Full evidence is in `reports/public/fireworks-pareto-v2.json`.
