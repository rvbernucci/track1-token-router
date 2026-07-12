# Sprint 77 - Local Router ML Recalibration

## Final Status

**Closed as `retain`; both contract-recalibrated neural candidates were rejected for runtime promotion.** The best candidate achieved 95.95% protected precision at 8.41% uniform coverage, but selected only sentiment and did not dominate the shipped pre-gate end to end. See `reports/public/router-ml-v3.md`. No `configs/e2b-router-ml-v3.json` is produced because the promotion gates were not jointly satisfied.

## Parallel Contract

This sprint runs concurrently with Sprint 76. It owns feature engineering, E2B correctness estimation, calibration and local-route thresholds. It may read the frozen Sprint 76 ledger as an additional teacher signal, but it must not train on the Sprint 76 sealed audit or influence its judgments.

## Objective

Improve selective local routing beyond sentiment-only without sacrificing the accuracy gate. Estimate calibrated probabilities for deterministic-solver success and E2B post-contract correctness, then release a local answer only where independent evidence supports the risk.

## Canonical Evidence

- [ ] Inventory all 4,400 balanced prompts from E2B expansion v1 and regression v2.
- [ ] Join prompt, FunctionGemma assessment, mechanical features, E2B answer, post-contract answer and correctness label by immutable task ID.
- [ ] Reject rows with missing assessments, conflicting labels, duplicate lineage or invalid provenance.
- [ ] Keep raw prompt text out of compact runtime features unless a frozen deterministic feature extractor produces it.
- [ ] Preserve source, category, difficulty and mutation lineage for grouped splitting.
- [ ] Record dataset hashes and exact row attrition reasons.

## Leakage-Safe Splits

- [ ] Group by mutation lineage before splitting.
- [ ] Keep the regression v2 final holdout and Sprint 76 sealed audit outside training and threshold selection.
- [ ] Use nested grouped cross-validation for model comparison.
- [ ] Fit feature normalization, clustering and imputation on training folds only.
- [ ] Prevent judge verdicts, gold answers, provider names and E2B correctness from entering inference features.
- [ ] Audit train-serving parity against features available inside the final container.

## Feature Families

- [ ] Include FunctionGemma intent plus five raw calibrated assessment scores.
- [ ] Include deterministic prompt features: length, token estimate, digits, operators, code markers, requested shape and explicit constraints.
- [ ] Include proof-engine capability signals without including solver answers or correctness labels.
- [ ] Include Answer Contract kind and mechanical verifiability indicators.
- [ ] Add source-agnostic interaction terms between intent, difficulty signals and output shape.
- [ ] Evaluate cluster distance and outlier features only as regression inputs, never as direct routing rules.
- [ ] Add missing-assessment and out-of-distribution indicators that force Fireworks-safe behavior.

## Candidate Models

- [ ] Fit per-intent regularized logistic regression as the transparent baseline.
- [ ] Compare histogram gradient boosting and Extra Trees offline.
- [ ] Compare one global model with per-intent heads against eight independent estimators.
- [ ] Calibrate probabilities with grouped out-of-fold isotonic or Platt calibration.
- [ ] Measure Brier score, log loss, AUROC, average precision and expected calibration error.
- [ ] Measure selective precision, Wilson lower bound, coverage and Fireworks-token savings.
- [ ] Reject candidates whose runtime representation requires heavy ML libraries in the final image.

## Two-Stage Decision Surface

- [ ] Stage 1 estimates whether the deterministic proof engine can return a uniquely verified answer.
- [ ] The proof engine remains the final authority; ML prediction alone can never release a deterministic answer.
- [ ] Stage 2 estimates whether E2B plus the Answer Contract Engine will be correct.
- [ ] Invalid FunctionGemma output, OOD features or failed contracts route directly to Fireworks.
- [ ] Use Wilson bounds as measured risk evidence rather than an unconditional global veto.
- [ ] Apply Nash/minimax utility only among candidates that already satisfy the accuracy floor.
- [ ] Optimize thresholds separately by intent and protected source.

## Promotion Gates

- [ ] Global selected local precision is at least `95%` on calibration and protected audits.
- [ ] Every promoted intent has at least 30 selected independent lineages.
- [ ] Wilson 90% lower bound is at least `85%` for each promoted intent.
- [ ] No protected source with at least 20 selected rows falls below `90%` observed precision.
- [ ] Coverage improves over the current sentiment-only policy without reducing protected precision.
- [ ] Brier score and expected calibration error do not regress against the current model.
- [ ] The serialized runtime scorer uses only standard-library arithmetic and frozen coefficients/trees.
- [ ] Unknown, missing or non-finite features fail closed to Fireworks.

## Stress And Ablation

- [ ] Remove each feature family and quantify marginal value.
- [ ] Compare score-only, mechanical-only and fused models.
- [ ] Replay sentiment-heavy, factual-heavy, code-heavy, math-heavy and uniform distributions.
- [ ] Test threshold sensitivity around every promoted cutoff.
- [ ] Simulate FunctionGemma score drift and intent confusion.
- [ ] Fuzz malformed assessments and extreme prompt lengths.
- [ ] Verify that local runtime remains within 4 GB RAM, 2 vCPU and ten minutes.

## Deliverables

- [ ] `scripts/build_router_ml_v3_ledger.py` creates the canonical joined ledger.
- [ ] `scripts/fit_router_ml_v3.py` performs grouped training, calibration and ablation.
- [ ] `scripts/replay_router_ml_v3.py` evaluates protected distributions and token economics.
- [ ] `reports/public/router-ml-v3.md` records cohorts, failures and promotion evidence.
- [ ] `configs/e2b-router-ml-v3.json` contains only a gate-approved lightweight runtime model.
- [ ] Unit tests reproduce feature order, coefficients, thresholds and fail-closed behavior.

## Definition Of Done

- [ ] A single hash-pinned candidate is chosen before protected holdouts are opened.
- [ ] Promotion or rejection is decided independently for every intent.
- [ ] The exact Docker image reproduces offline scorer decisions byte-for-byte.
- [ ] Any rejected experiment remains documentation and does not enter runtime.
