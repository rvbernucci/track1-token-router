# Sprint 72 - Cluster-Augmented E2B Regression

## Timebox

`60 minutes`. Promote only the smallest already-supported feature set; defer exploratory clustering variants.

## Objective

Estimate `P(E2B correct)` per intent using FunctionGemma scores, mechanical features and frozen cluster geometry. Clustering discovers local task families; supervised regression remains the decision model.

## Experimental Contract

- [x] Keep the E2B correctness label out of every clustering feature.
- [x] Fit cluster geometry on `fit` rows only.
- [x] Compare score-only, compact and full mechanical feature spaces.
- [x] Compare K-Means, DBSCAN and HDBSCAN as discovery tools.
- [x] Confirm that cluster-only policies fail at least one protected distribution and must not be promoted directly.

## Cluster-Augmented Features

- [x] Freeze compact K-Means centroids independently for each predicted intent.
- [x] Add one-hot cluster membership to the supervised feature vector.
- [x] Add distance to the nearest centroid.
- [x] Add distance divided by the cluster's frozen fit radius.
- [x] Add an outlier indicator when the prompt falls outside every approved radius.
- [x] Keep cluster IDs and geometry deterministic under seed `72`.
- [x] Persist candidate centroids, radii, normalization and feature order in the generated benchmark artifact.
- [x] Do not add runtime distance code because no cluster candidate passed promotion.

## Supervised Models

- [x] Fit one regularized logistic model per predicted intent.
- [x] Compare base regression against cluster-augmented regression using identical splits.
- [x] Keep geometry fit-only and labels out of the clustering stage.
- [x] Select thresholds using `calibration` only.
- [x] Measure Brier score, log loss, AUROC, average precision and calibration error.
- [x] Record coverage, precision and support by intent and protected source.
- [x] Exclude invalid FunctionGemma assessments and keep them Fireworks-only.

## Protected Audit

- [x] Open expansion, historical and boundary rows only for final audit.
- [x] Require no protected source with support at least 20 to fall below `85%` observed precision.
- [x] Reject every unsupported factual, code, logic, math, NER and summarization cohort.
- [x] Preserve the existing sentiment-only v2 route because cluster augmentation did not beat it.

## Gates

- [x] Cluster features failed to improve calibration or safe coverage; promotion was rejected.
- [x] Minimum selected support remained `20` for every candidate considered.
- [x] The sentiment candidate reached `90%` calibration precision but was inferior to the `90.91%` base.
- [x] Direct cluster policies failed protected-source stability and were rejected.
- [x] No cluster artifact enters runtime, so unknown-cluster behavior remains the existing Fireworks-safe path.

## Definition of Done

- [x] The offline candidate is reproducible; no ML library or rejected geometry is added to Docker.
- [x] No intent was promoted, and the rejection evidence is separated by intent and protected source.
