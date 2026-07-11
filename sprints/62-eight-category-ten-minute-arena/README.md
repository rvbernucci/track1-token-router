# Sprint 62 - Eight-Category Ten-Minute Arena

## Objective

Measure the exact hybrid image on a lineage-separated, representative batch spanning all eight Track 1 categories and verify that routing remains within the ten-minute evaluator envelope.

## Dataset

- [ ] Include factual Q&A, math reasoning, sentiment, summarization, NER, code debugging, logic puzzles and code generation.
- [ ] Use balanced categories and a mixture of short, medium and long prompts.
- [ ] Exclude every training row, exact duplicate and sealed evaluation answer.
- [ ] Include deterministic, E2B-favorable and Fireworks-required cohorts.
- [ ] Freeze task IDs, prompt hashes and expected answer contracts before execution.

## Measurements

- [ ] End-to-end wall time, cold start and per-task latency.
- [ ] FunctionGemma p50, p95 and timeout rate.
- [ ] E2B p50, p95, decode ceiling and truncation rate.
- [ ] Fireworks prompt, completion and total tokens.
- [ ] Route distribution and fallback reasons by category.
- [ ] Peak cgroup memory and process high-water RSS.
- [ ] Answer-contract validity and conservative correctness.

## Gates

- [ ] Entire batch completes within `570 seconds`, retaining a 30-second reserve.
- [ ] Peak cgroup memory is at most `3584 MiB`.
- [ ] Overall answer-contract validity is `100%`.
- [ ] Local release precision is at least `80%` and reported with Wilson 95% lower bound.
- [ ] Runtime failure rate is at most `2%`.
- [ ] All eight categories contain at least one successful answer.
- [ ] Remote token use is strictly below the always-Fireworks baseline.

## Evidence

- `evals/full-local-arena/tasks.json`
- `reports/generated/full-local/arena-results.jsonl`
- `reports/generated/full-local/arena-summary.json`
- `reports/public/full-local-arena.md`

## Command

```bash
python3 scripts/run_full_local_arena.py \
  --image ghcr.io/rvbernucci/track1-token-router:v3.0.0-full-local \
  --tasks evals/full-local-arena/tasks.json \
  --deadline-seconds 570 --json
```

## Completion Decision

If the exact batch misses memory or time limits, reduce local probes before changing model quantization or output ceilings.
