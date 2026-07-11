# E2B Boundary Audit

Decision: `reject_or_restrict_0.75`

- Rows: `480`
- Selected at 0.75: `60`
- Precision: `95.00%`
- Coverage: `12.50%`
- Wilson lower 95%: `86.30%`
- Brier score: `0.2911`

## Gates

- [x] `all_480_rows_evaluated`
- [x] `unique_unseen_prompt_hashes`
- [ ] `at_least_100_selected`
- [x] `precision_at_least_82pct`
- [x] `wilson_lower_at_least_75pct`
- [x] `intent_precision_floor`
- [x] `assessment_validity_at_least_98pct`
- [x] `invalid_assessment_routes_fireworks`

## Probability Bands

- `0.00-0.65`: rows `420`, precision `64.29%`
- `0.65-0.70`: rows `0`
- `0.70-0.75`: rows `0`
- `0.75-0.80`: rows `60`, precision `95.00%`
- `0.80-0.90`: rows `0`
- `0.90-1.01`: rows `0`
