# E2B Contract v2 Matrix Regression

Date: 2026-07-10

## Objective

Predict when the local Gemma E2B answer can replace Fireworks after Answer Contract Engine v2. The model trains on all 1,991 rows: `correct=1`; `incorrect` and `uncertain=0`. Training on only the 728 positives would not learn the rejection boundary.

## Five-Parameter Signal

| FunctionGemma parameter | Correct mean | Incorrect mean | Direction |
|---|---:|---:|---|
| deterministic fit | 3.293 | 3.410 | weak |
| reasoning demand | 4.067 | 4.727 | lower is safer |
| knowledge uncertainty | 0.749 | 0.880 | lower is safer |
| generation demand | 3.179 | 4.936 | strongest lower-is-safer signal |
| format complexity | 4.475 | 5.630 | lower is safer |

The strongest pre-response negative coefficients are generation demand, generation-by-format interaction, input-length-by-generation interaction, reasoning demand and format complexity. The strongest post-response positive signals are mechanical validator validity, terminal completion and lexical overlap. Long answers, high answer/prompt ratio and likely token-cap truncation reduce acceptance probability.

## Conservative Threshold

Validation selected `pre_probability >= 0.30` and `post_probability >= 0.85`. Selection prioritizes the Wilson lower bound and local E2B accuracy before coverage. Kimi quality is not part of the acceptance label: a correct E2B answer is accepted even when Kimi is also correct or more verbose.

| Metric | Validation | Locked test |
|---|---:|---:|
| selected coverage | 12.7% (36 rows) | 12.9% (37 rows) |
| local accuracy | 88.9% | 86.5% |
| Wilson lower 95% | 74.7% | 72.0% |
| saved Fireworks tokens | 6,835 | 6,650 |
| hybrid correct minus Kimi (diagnostic only) | +1 | -2 |

## Decision

Do not enable the policy yet because this test split has already been inspected and is not a fresh promotion holdout. The observed 36.6% E2B correctness rate is a retrospective upper bound, not predictable safe coverage. The current regression identifies roughly 13% of tasks with high local precision and passes its binary local-accuracy diagnostic. A genuinely fresh holdout is still required before promotion.

Candidate artifact: `configs/e2b-selective-policy-contract-v2-candidate.json` with `default_enabled=false`.
