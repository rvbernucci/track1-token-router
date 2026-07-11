# E2B Routing Cohorts

Coverage depends on the hidden input distribution; it is not a fixed global percentage.

## Locked Cohorts

| Category | Selected | Test rows | Coverage | Precision |
|---|---:|---:|---:|---:|
| code_debugging | 2 | 43 | 4.7% | 100.0% |
| code_generation | 0 | 35 | 0.0% | n/a |
| factual_qa | 4 | 24 | 16.7% | 50.0% |
| logic_puzzle | 3 | 43 | 7.0% | 100.0% |
| math_reasoning | 0 | 23 | 0.0% | n/a |
| ner | 10 | 38 | 26.3% | 90.0% |
| sentiment | 16 | 35 | 45.7% | 87.5% |
| summarization | 2 | 45 | 4.4% | 100.0% |

## Input-Mix Scenarios

| Scenario | Local coverage | Local precision | Local / 100 | Saved tokens / 100 |
|---|---:|---:|---:|---:|
| balanced | 13.1% | 84.1% | 13.1 | 2354 |
| sentiment_heavy | 36.8% | 87.5% | 36.8 | 6608 |
| extraction_classification | 33.0% | 88.1% | 33.0 | 5931 |
| code_reasoning_heavy | 5.8% | 87.0% | 5.8 | 1039 |
| observed_locked_mix | 12.9% | 86.5% | 12.9 | 2325 |

Coverage is distribution-dependent. Factual QA is unstable across splits and should remain remote until a fresh holdout confirms its local precision.
