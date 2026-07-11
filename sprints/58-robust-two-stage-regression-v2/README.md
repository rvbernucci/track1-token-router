# Sprint 58 - Robust Two-Stage Regression V2

Status: **Completed - candidate fitted but not nominated**

## Objective

Fit a stable policy that separates the decision to spend local runtime on E2B from the decision to release its answer. Optimize accuracy first, stability second and Fireworks token savings third.

## Runtime Decisions

```text
Stage A, before E2B:
  estimate P(E2B will produce a releasable candidate)
  choose probe or Fireworks under deadline and memory constraints

Stage B, after E2B:
  Answer Contract + registered hard verifier
  release only with valid evidence and a robust probability margin
  otherwise use Fireworks
```

Stage A can waste local time but cannot authorize a local answer. Stage B cannot override a failed proof, execution, grounding or output contract.

## Deliverables

- Reduced input-only feature contract for Stage A.
- Proof-gated post-response feature contract for Stage B.
- Grouped train/validation pipeline with no final-holdout access.
- Model comparison across regularized and monotonic candidates.
- Robust threshold search with an explicit abstention band.
- Game-theoretic expected-utility selector using scored tokens, latency and risk.
- Disabled-by-default v2 policy artifact and full coefficient diagnostics.

## Checklist

### Stage A Features And Target

- [x] Use only features available before E2B inference.
- [x] Include FunctionGemma intent and five anchored scores.
- [x] Include requested output shape, input length and deadline ratio.
- [x] Include registered-verifier availability without candidate evidence.
- [x] Keep the final selected feature set at 24 dimensions or fewer.
- [x] Remove duplicate, near-constant and strongly collinear signals.
- [x] Define positive target as an E2B result eligible for safe local release.
- [x] Never use E2B answer text, post evidence or judge verdict as a Stage A feature.

### Stage B Safety

- [x] Require Answer Contract validity before probability evaluation.
- [x] Require a registered hard verifier for every promoted cohort.
- [x] Make failed proof, execution or grounding an unconditional Fireworks route.
- [x] Keep open-world factual QA remote.
- [x] Separate thresholds by verifier family only with sufficient lineages.
- [x] Require probability to clear threshold plus a frozen safety margin.
- [x] Preserve unsupported semantic-only cohorts as disabled.

### Model Fitting

- [x] Fit L1 and L2 logistic baselines.
- [x] Compare reduced linear, monotonic and calibrated candidates.
- [x] Use grouped folds by template and mutation lineage.
- [x] Select features, coefficients and thresholds on train/validation only.
- [x] Calibrate probabilities with a method fitted on validation only.
- [x] Report Brier score, ECE, PR curve and coefficient uncertainty.
- [x] Bootstrap coefficients and outcomes by lineage.
- [x] Reject perfect-separation artifacts and unstable sparse coefficients.

### Robust Thresholds

- [x] Freeze a probability perturbation radius of at least `0.02`.
- [x] Test pre and post probabilities independently and jointly.
- [x] Perturb every FunctionGemma score by `+/-1` within bounds.
- [x] Add an abstention band at least as wide as the perturbation radius.
- [x] Measure route agreement across bootstrap refits.
- [x] Optimize Wilson lower precision before local coverage.
- [x] Optimize Fireworks tokens only after every accuracy/stability gate passes.
- [x] Evaluate balanced, sentiment/NER-heavy and code/math-heavy mixtures.

### Expected Utility

- [x] Estimate expected Fireworks tokens avoided by cohort.
- [x] Penalize E2B p95 latency and deadline-exhaustion risk.
- [x] Treat local inference as zero scored tokens but non-zero runtime.
- [x] Compare E2B probe utility with immediate Fireworks fallback.
- [x] Prove that no game-theory term can bypass the accuracy gate.
- [x] Log the probability, utility components, policy hash and final route.

## Metrics

- Stage A precision, recall and avoidable-probe rate;
- post-release precision, Wilson lower bound and coverage;
- false-local release and verifier-invalid release counts;
- perturbation and bootstrap route-flip rates;
- Brier score and expected calibration error;
- coefficient sign and selection stability;
- Fireworks tokens saved with lineage bootstrap interval;
- latency cost of failed E2B probes by input mix.

## Promotion Gate

- Local release precision at least 95%, with Wilson lower 95% at least 90%.
- Zero verifier-invalid and zero unsupported factual releases.
- Probability perturbation flip rate below 5%, with a target below 2%.
- FunctionGemma score-shift flip rate below 5%.
- Bootstrap route agreement at least 95%.
- Every enabled family has at least 100 independent development lineages.
- Lower 95% confidence bound for Fireworks token savings is positive.
- Policy remains `default_enabled=false` until Sprint 59 passes.

## Completion Contract

- Command: `python3 scripts/fit_e2b_regression_v2.py --fresh-holdout=false --check`.
- Versioned artifact: `configs/e2b-local-adjudication-v2-candidate.json`.
- Evidence report: `reports/generated/e2b-regression-v2-calibration.md`.
- Decision record: nominate one exact candidate or retain the disabled v1 policy.
- Dependency: consumes Sprint 57 development labels; feeds Sprint 59.

## Anti-Scope

- Do not select thresholds on the final holdout.
- Do not optimize aggregate accuracy while hiding weak cohorts.
- Do not use Kimi superiority as the target label.
- Do not release candidates based on probability without hard evidence.
- Do not relax a gate after observing its result.

## Completion Evidence

- Fit firewall: only 1,192 valid train rows and 400 valid validation rows were opened; eight invalid development assessments are direct-Fireworks examples. No sealed path exists in the fitter.
- Feature contract: 23 input-only dimensions containing FunctionGemma intent, five scores, requested shape, normalized input length, deadline ratio and pre-response verifier availability.
- Models: L1, L2 and monotonic logistic candidates compared for deterministic and E2B targets; Platt calibration fitted on validation only.
- Stability: `+/-0.02` independent/joint probability perturbation, every FunctionGemma score shifted by `+/-1`, lineage bootstrap refits and three input-mixture scenarios.
- Validation: two proof-gated E2B releases, both correct, but Wilson lower 95% only `34.24%`; bootstrap route agreement `90.25%`.
- Decision: nomination rejected because Wilson, bootstrap stability and token-savings lower-bound gates failed. Thresholds were not relaxed after observing results.
- Artifact: `configs/e2b-local-adjudication-v2-candidate.json` remains `default_enabled=false`.
- Verification: `python3 scripts/fit_e2b_regression_v2.py --fresh-holdout=false --check` passes the completion contract without opening the final holdout.

## Promotion Decision

Retain the runtime's disabled local E2B policy for now. Carry this exact frozen candidate into Sprint 59 for one-time sealed evaluation; invalid FunctionGemma output always bypasses both regressions and routes directly to Fireworks.
