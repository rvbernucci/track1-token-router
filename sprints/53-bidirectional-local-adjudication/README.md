# Sprint 53 - Bidirectional Local Adjudication

Status: **Completed - candidate rejected by stability gate and left disabled**

## Objective

Integrate deterministic proofs, E2B candidates and FunctionGemma features into one fail-closed adjudication protocol. Improve the regression so it predicts “E2B satisfies the task” rather than “E2B beats Kimi.”

## Binary Runtime Contract

```text
E2B correct + contract satisfied + verifier accepted -> local
everything else -> Fireworks
```

Kimi quality is diagnostic only. A correct local answer is valid even when Kimi would also be correct or more elaborate.

## Deliverables

- `LocalAdjudicationEvidence` schema.
- Verifier registry with capability, proof type and confidence source.
- Two-stage logistic model: pre-probe and post-answer acceptance.
- Cohort-aware calibration by intent and verifier family.
- Abstention policy for distribution shift and low sample size.
- Replay tool producing exact route, proof, probability and rejection reason.
- Versioned candidate policy with `default_enabled=false` until fresh promotion.

## Checklist

### Evidence Fusion

- [x] Keep FunctionGemma perception separate from engine selection.
- [x] Add proof validity, proof uniqueness and verifier family as features.
- [x] Add deterministic/E2B agreement and normalized-answer equality.
- [x] Add post-answer truncation, grounding and execution signals.
- [x] Preserve raw prompt and candidate isolation.
- [x] Prevent model-provided confidence from becoming a hard proof signal.

### Regression

- [x] Train on all labels: correct `1`, incorrect/uncertain `0`.
- [x] Split by mutation lineage and template family.
- [x] Compare logistic linear, nonlinear and monotonic calibrated variants.
- [x] Optimize Wilson lower precision before coverage.
- [x] Calibrate thresholds per verifier family only with sufficient samples.
- [x] Measure expected calibration error and Brier score.
- [x] Bootstrap confidence intervals by lineage.

### Distribution Shift

- [x] Detect intent-mix and score-distribution drift.
- [x] Simulate balanced, sentiment-heavy, extraction-heavy and code-heavy batches.
- [x] Reduce coverage automatically when a cohort leaves its calibrated envelope.
- [x] Keep factual QA remote until fresh evidence resolves observed instability.
- [x] Never infer 36.6% safe coverage from retrospective labels alone.

### Runtime

- [x] Probe E2B only when pre-probability and remaining deadline permit.
- [x] Release only when post-probability, proof and Answer Contract gates pass.
- [x] Trace every probability, coefficient version and proof result.
- [x] Fall back to Fireworks on any parser, verifier or policy failure.
- [x] Keep all model authorization constrained by runtime `ALLOWED_MODELS`.

## Metrics

- local released precision and Wilson lower bound;
- local coverage overall and by cohort;
- false-local release rate;
- abstention rate;
- calibration error/Brier score;
- expected tokens saved under each input mix;
- p95 local adjudication latency;
- policy stability under score perturbation.

## Promotion Gate

- Fresh holdout local precision at least 85%, Wilson lower bound at least 75%.
- Zero verifier-invalid answers released.
- Coverage improvement is reported separately from accuracy.
- No cohort is enabled with fewer than 20 independent lineage groups.
- The policy remains disabled if the holdout has been used for threshold selection.

## Completion Contract

- Planned command: `python3 scripts/fit_local_adjudication_policy.py --fresh-holdout --check`.
- Versioned artifact: `configs/local-adjudication-policy-v1.json`.
- Evidence report: `reports/generated/local-adjudication-calibration.md`.
- Decision record: `default_enabled=true` only after the fresh holdout gate; otherwise preserve a disabled candidate with full diagnostics.
- Dependency: consumes promoted proof/verification features from Sprints 50-52 and produces the candidate runtime policy for Sprint 54.

## Anti-Scope

- Do not require E2B to outperform Kimi.
- Do not label judge disagreement as correct.
- Do not tune coefficients on the locked test.
- Do not enable a category solely because its retrospective accuracy is high.

## Completion Evidence

- Dataset: 731 rows with 294 correct, 297 incorrect and 140 uncertain labels; train/validation/fresh-holdout groups are disjoint by both mutation lineage and template family.
- Calibration: every enabled verifier family has at least 36 independent development lineages; linear logistic was selected after comparison with constant, nonlinear logistic and monotonic calibrated variants.
- Fresh holdout: 42/104 candidates would release locally, all 42 correct; precision 100%, Wilson lower 95% 91.62%, zero verifier-invalid releases and 40.38% measured coverage.
- Actual E2B replay: after adding three source-instruction counterexamples, 21/21 retrospectively accepted candidates were judge-correct; this reused evidence remained diagnostic only.
- Calibration quality: holdout Brier approximately 0.0004 and expected calibration error approximately 0.0163.
- Runtime: p95 evidence latency below 30 ms; lineage bootstrap precision interval remained 100%-100%.
- Safety failure: ±0.02 probability perturbation changed 14/196 route comparisons (7.14%), exceeding the predeclared 5% stability gate.
- Artifact: `configs/local-adjudication-policy-v1.json` is intentionally `default_enabled=false` and pins the dataset plus all three verifier policies and runtime implementation.
- Replay: `python3 scripts/replay_local_adjudication.py --check` emits exact route, probabilities, policy hash and proof evidence with zero false-local releases.

## Promotion Decision

Do not promote this policy. `python3 scripts/fit_local_adjudication_policy.py --fresh-holdout --check` correctly exits non-zero because the stability gate failed, even though accuracy and Wilson gates passed. The candidate remains available for Sprint 54 shadow testing, but the production path falls back to Fireworks for every task. A future promotion requires a newly calibrated threshold policy and another untouched confirmation set; this holdout must not be reused for that decision.
