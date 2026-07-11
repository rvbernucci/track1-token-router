# Distribution Shift And Token Economics

Decision: `PASS`

- Frozen ledger rows: `96`
- Seeded random mixtures: `1000`
- Random minimum accuracy: `86.46%`
- Random minimum token savings: `2778`
- Break-even: `No feasible category mixture reaches zero savings.`

## Observed-Ledger Scenarios

| Scenario | Accuracy | Local coverage | Local precision | Token savings | CI95 | Worst runtime projection |
|---|---:|---:|---:|---:|---:|---:|
| `balanced` | 96.93% | 24.99% | 95.92% | 3671 | 3345..4044 | 660.0s |
| `sentiment_ner_heavy` | 93.74% | 39.86% | 92.85% | 4603 | 4132..5073 | 667.2s |
| `code_heavy` | 96.22% | 9.93% | 95.60% | 3137 | 2932..3373 | 725.2s |
| `math_logic_heavy` | 98.77% | 39.94% | 98.96% | 3801 | 3527..4091 | 524.1s |
| `fireworks_heavy` | 97.20% | 0.00% | 100.00% | 2785 | 2774..2802 | 768.0s |
| `local_favorable` | 95.87% | 100.00% | 95.87% | 6337 | 6084..6616 | 336.7s |
| `long_context_heavy` | 92.81% | 62.44% | 90.24% | 5674 | 5448..5923 | 618.2s |

## Gates

- [x] `accuracy_gate_all_scenarios`
- [x] `local_precision_at_least_80pct`
- [x] `required_scenarios_save_tokens`
- [x] `runtime_bounded_or_safe_policy`
- [x] `authorization_scenarios_valid`
- [x] `lineage_aware_confidence_intervals`
- [x] `policy_frozen_before_comparison`
- [x] `at_least_1000_mixtures`

Observed accuracy and token values come from the frozen ledger. Runtime-at-7s and sensitivity values are projections, not measurements.
