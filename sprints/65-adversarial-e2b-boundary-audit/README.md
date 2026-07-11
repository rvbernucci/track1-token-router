# Sprint 65 - Adversarial E2B Boundary Audit

## Objective

Measure false-positive risk and train-serving skew around the promoted E2B threshold `0.75` before attempting any increase in local coverage.

## Dataset

- [x] Generate 480 unseen prompts, 60 per Track 1 category.
- [x] Create independent mutation lineages rather than paraphrases of training rows.
- [x] Measure all requested probability bands. Runtime predictions collapsed into `0.00-0.65` and `0.75-0.80`; the missing bands are recorded as model behavior rather than fabricated through post-selection.
- [ ] Include short, long, ambiguous, multilingual, negated and strict-format prompts. This first sealed corpus is English and mechanically scorable; the limitation prevents a broad keep decision.
- [x] Hash prompts and freeze train, calibration and sealed test splits before inference.
- [x] Verify zero exact or normalized duplicates against 4,000 prior rows.

## Execution

- [x] Run the embedded FunctionGemma endpoint used by the final image.
- [x] Preserve raw assessment, calibrated assessment, matrix probability and route decision.
- [x] Run E2B at the frozen 96-token ceiling for every valid assessment.
- [x] Apply the exact production Answer Contract Engine without semantic rewriting.
- [x] Produce independent correctness labels with mechanical validators.
- [x] Avoid judge calls because every gold answer is fixed and mechanically scorable.
- [x] Treat timeout, malformed output and missing labels as not correct.

## Analysis

- [x] Measure precision, coverage and Wilson 95% lower bound by probability band.
- [x] Measure false-positive rate by intent, output shape, prompt length and language.
- [x] Compare runtime precision (`95.00%`) with the grouped OOF expectation (`84.52%`).
- [x] Compute Brier score and probability-band reliability evidence.
- [x] Detect intent-specific score-distribution collapse: only sentiment crossed `0.75`.
- [x] List the smallest counterexamples that cross `0.75` and fail.

## Gates

- [x] Zero normalized overlap with 4,000 prior rows.
- [ ] At least 100 evaluated rows at or above `0.75`: observed `60`.
- [x] Precision at `0.75` is at least `82%`: observed `95.00%`.
- [x] Wilson 95% lower bound at `0.75` is at least `75%`: observed `86.30%`.
- [x] No intent with at least 20 selected rows has precision below `70%`.
- [x] Runtime decision and recomputed threshold decision agree for every row.
- [x] Malformed or invalid assessments always route to Fireworks.

## Evidence

- `evals/e2b-boundary-v1/manifest.json`
- `evals/e2b-boundary-v1/sealed/tasks.jsonl`
- `reports/generated/e2b-boundary-v1/predictions.jsonl`
- `reports/generated/e2b-boundary-v1/adjudication.jsonl`
- `reports/public/e2b-boundary-audit.md`

## Command

```bash
python3 scripts/run_e2b_boundary_audit.py \
  --threshold 0.75 \
  --tasks evals/e2b-boundary-v1/sealed/tasks.jsonl \
  --check --json
```

## Completion Decision

Status: **complete with a restrictive decision**.

Run [29166932565](https://github.com/rvbernucci/track1-token-router/actions/runs/29166932565) evaluated all 480 rows in the exact final image under 4 GB RAM, 2 vCPU and no network. The audit rejected broad E2B enablement because only 60 rows crossed the threshold. Those rows were all sentiment tasks, with 57 correct (`95.00%` precision, `86.30%` Wilson lower bound). The production matrix policy now explicitly permits only `sentiment`; every other intent fails closed to Fireworks. The threshold remains `0.75` and was not tuned on this sealed corpus.
