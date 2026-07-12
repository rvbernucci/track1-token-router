# Router ML v3 - Contract-Recalibrated Neural Audit

## Decision

**Reject both neural candidates for runtime promotion. Retain the shipped matrix gate.**

The contract-recalibrated experiment produced a stronger probability estimator and passed the protected precision floor, but it did not safely expand routing beyond sentiment and did not prove end-to-end dominance over the broader shipped local cohort. The best artifact remains reproducible research evidence and is not copied into the Docker runtime.

## Canonical Population And Labels

- 4,400 balanced tasks across the eight official categories.
- 2,640 fit, 880 calibration and 880 protected-holdout rows.
- Gemma 4 E2B responses used the generic contract prompt promoted in `v3.8.2-e2b-contract`.
- Mechanical evidence decided 2,621 rows: 1,553 correct and 1,068 incorrect.
- GLM-5.2 plus the assigned Codex/Antigravity judge evaluated 1,779 semantic rows.
- The semantic pair agreed on 1,721/1,779 rows (96.74%). The 58 unresolved disagreements failed closed to incorrect.
- Final labels: 2,183 correct and 2,217 incorrect.
- Contract ledger SHA-256: `34fa0d383915e91c3c4c60e44a9ce8049f93213028a3d6b31b6669c5c833dc8d`.

Protected labels remained absent from training, calibration and threshold selection. They were opened once after each candidate and threshold surface had been serialized.

## AMD GPU Search

| Candidate | Search | Grouped OOF AUROC | Brier | Protected result | Coverage |
|---|---|---:|---:|---:|---:|
| Fast | 12 global configs, 4/intent, 3 seeds, 4 folds, 250 epochs | **0.87385** | **0.14351** | **71/74 (95.95%)** | **8.41%** |
| Full | 24 global configs, 8/intent, 5 seeds, 5 folds, 500 epochs | 0.87318 | 0.14432 | 63/66 (95.45%) | 7.50% |

Both searches ran with PyTorch 2.9 on the AMD ROCm pod. The larger search did not dominate the fast candidate. The fast candidate is therefore the experiment champion.

## Selective Surface

Only sentiment satisfied all calibration gates.

| Candidate | Calibration selection | Precision | Wilson lower 90% | Threshold |
|---|---:|---:|---:|---:|
| Fast | 34/35 | 97.14% | 88.16% | 0.899075 |
| Full | 31/32 | 96.88% | 87.14% | 0.910749 |

Every other intent received threshold `1.0`, meaning Fireworks-safe rejection. The models showed ranking signal in several categories, but no other category had enough independent, high-confidence support to satisfy precision, Wilson and minimum-support gates simultaneously.

## Why The Candidate Is Rejected

1. It does not achieve Sprint 77's objective of safely expanding beyond sentiment.
2. The scorer uses post-answer contract and proof features. It can validate an E2B response after inference, but cannot by itself decide which prompts should incur local inference before that response exists.
3. Replacing the shipped pre-gate would reduce local coverage; layering the scorer after the current gate has not demonstrated end-to-end accuracy dominance.
4. Stage 1 ML for deterministic routing is intentionally not promoted: the proof engine is cheaper, exact and remains the sole authority for releasing deterministic answers.
5. No neural artifact is embedded in the image, so the 4 GB / 2 vCPU runtime remains unchanged.

## Frozen Artifacts

- Fast candidate: `evals/router-ml-v3/candidate-contract-v2-fast-rejected.json`
  - SHA-256: `ffb24b764aef7f8cf3ce4a866f292635f71d1e8cfd849ce4776fa8eecbcb44d4`
- Full candidate: `evals/router-ml-v3/candidate-contract-v2-full-rejected.json`
  - SHA-256: `b27e1887df3ebd3d7fe5b253c0f94694ed6417d15f45932674594276ff79eb3c`

The runtime continues to use `configs/e2b-category-matrix-regression-v2.json`. Rejected neural artifacts cannot expand or modify production routing.
