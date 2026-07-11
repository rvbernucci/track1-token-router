# Sprint 65 - Adversarial E2B Boundary Audit

## Objective

Measure false-positive risk and train-serving skew around the promoted E2B threshold `0.75` before attempting any increase in local coverage.

## Dataset

- [ ] Generate at least 480 unseen prompts, 60 per Track 1 category.
- [ ] Create independent mutation lineages rather than paraphrases of training rows.
- [ ] Oversample predicted probabilities in bands `0.65-0.70`, `0.70-0.75`, `0.75-0.80` and `0.80-0.90`.
- [ ] Include short, long, ambiguous, multilingual, negated and strict-format prompts.
- [ ] Hash prompts and freeze train, calibration and sealed test splits before inference.
- [ ] Verify zero exact or normalized duplicates against all 3,982 regression rows.

## Execution

- [ ] Run the embedded FunctionGemma endpoint used by the final image.
- [ ] Preserve raw assessment, calibrated assessment, matrix probability and route decision.
- [ ] Run E2B at the frozen 96-token ceiling for every valid assessment.
- [ ] Apply the exact production Answer Contract Engine without semantic rewriting.
- [ ] Produce independent correctness labels with mechanical validators where possible.
- [ ] Use conservative multi-judge adjudication only for non-mechanical cases.
- [ ] Treat disagreement, timeout, malformed output and missing labels as not correct.

## Analysis

- [ ] Measure precision, coverage and Wilson 95% lower bound by probability band.
- [ ] Measure false-positive rate by intent, output shape, prompt length and language.
- [ ] Compare raw-score runtime predictions with grouped OOF expectations.
- [ ] Compute calibration error, Brier score and reliability curves.
- [ ] Detect intent-specific coefficient drift and score-distribution shift.
- [ ] List the smallest counterexamples that cross `0.75` and fail.

## Gates

- [ ] Zero lineage overlap with training or prior holdouts.
- [ ] At least 100 evaluated rows at or above `0.75`.
- [ ] Precision at `0.75` is at least `82%`.
- [ ] Wilson 95% lower bound at `0.75` is at least `75%`.
- [ ] No intent with at least 20 selected rows has precision below `70%`.
- [ ] Train-serving route disagreement is below `2%`.
- [ ] Malformed or invalid assessments always route to Fireworks.

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

Keep `0.75` only if every hard gate passes. Raise the threshold or disable affected intents when false positives concentrate near the boundary. Never lower the threshold from this dataset.
