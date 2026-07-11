# Proof-Carrying Math And Logic

- gate: `True`
- rows: `260`
- released: `180`
- false positives: `0`
- false negatives: `0`
- released precision: `100.000%`
- Wilson lower 95%: `97.910%`
- math p95: `0.106 ms`
- logic p95: `0.110 ms`

## Families

| Family | Rows | Released | Correct releases | False positives | Refused |
|---|---:|---:|---:|---:|---:|
| assignment_underdetermined | 8 | 0 | 0 | 0 | 8 |
| decimal_ast | 20 | 20 | 20 | 0 | 0 |
| divide_by_zero | 8 | 0 | 0 | 0 | 8 |
| finite_assignment | 10 | 10 | 10 | 0 | 0 |
| inexact_without_rounding | 8 | 0 | 0 | 0 | 8 |
| invalid_converse | 8 | 0 | 0 | 0 | 8 |
| ordering | 20 | 20 | 20 | 0 | 0 |
| ordering_cycle | 8 | 0 | 0 | 0 | 8 |
| ordering_disconnected | 8 | 0 | 0 | 0 | 8 |
| percentage | 30 | 30 | 30 | 0 | 0 |
| percentage_change | 20 | 20 | 20 | 0 | 0 |
| proportional_rate | 20 | 20 | 20 | 0 | 0 |
| propositional | 20 | 20 | 20 | 0 | 0 |
| quantified | 20 | 20 | 20 | 0 | 0 |
| quantifier_mismatch | 8 | 0 | 0 | 0 | 8 |
| unit_conversion | 20 | 20 | 20 | 0 | 0 |
| unit_mismatch | 8 | 0 | 0 | 0 | 8 |
| unsafe_expression | 8 | 0 | 0 | 0 | 8 |
| unused_number | 8 | 0 | 0 | 0 | 8 |

## Gate

- [x] `zero_false_positive`
- [x] `precision_at_least_95`
- [x] `wilson_lower_above_90`
- [x] `math_p95_below_100_ms`
- [x] `logic_p95_below_500_ms`
- [x] `static_security`
