# Sprint 62 - Eight-Category Ten-Minute Arena

## Objective

Measure the exact hybrid image on a lineage-separated, representative batch spanning all eight Track 1 categories and verify that routing remains within the ten-minute evaluator envelope.

## Dataset

- [x] Include factual Q&A, math reasoning, sentiment, summarization, NER, code debugging, logic puzzles and code generation.
- [x] Use 10 lineage-separated final-holdout rows per category.
- [x] Keep runtime inputs separate from sealed labels.
- [x] Include verified deterministic and Fireworks-required cohorts; retain exact-image E2B evidence separately.
- [x] Freeze task IDs, prompt hashes and expected answer contracts before execution.

## Measurements

- [x] Record exact-image cold/warm timing and a conservative 80-row runtime projection.
- [x] Preserve exact FunctionGemma and E2B container evidence from Sprint 60.
- [x] Record Fireworks total tokens against an always-remote baseline.
- [x] Record route distribution by category.
- [x] Record exact-image sampled peak container memory.
- [x] Record answer-contract validity and conservative correctness.

## Gates

- [x] Conservative runtime projection is `243.693 seconds`, below `570 seconds`.
- [x] Exact-image sampled peak memory is `728.1 MiB`, below `3584 MiB`.
- [x] Overall answer-contract validity is `100%`.
- [x] Verified local precision is `100%`; Wilson 95% lower bound is `91.24%`.
- [x] Runtime failure rate is `0%` in the frozen arena.
- [x] All eight categories contain at least one successful answer.
- [x] Remote tokens are `1,145` versus `2,676` always-Fireworks, a `57.21%` reduction.

## Evidence

- `evals/full-local-arena/tasks.json`
- `reports/generated/full-local/arena-results.jsonl`
- `reports/generated/full-local/arena-summary.json`
- `reports/public/full-local-arena.md`

## Command

```bash
python3 scripts/run_full_local_arena.py \
  --image ghcr.io/rvbernucci/track1-token-router:v3.2.0-full-hybrid \
  --tasks evals/full-local-arena/tasks.json \
  --deadline-seconds 570 --json
```

## Completion Decision

Passed as a layered evidence gate. The lineage-separated 80-row replay passes accuracy, contract and token gates; exact-image measurements support the runtime and memory envelope. The report explicitly does not claim a live 80-row image execution. Promote to Sprint 63.
