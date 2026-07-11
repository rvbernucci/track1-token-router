# Final Pareto Calibration

Decision: `PASS`

- Live Fireworks calls: `46`.
- Estimated spend: `$0.003703`.
- Selected Fireworks policy: `intent_policy`.
- Selected E2B threshold: `0.75`.
- Versioned policy: `configs/fireworks-intent-policy-v2.json`.

## Candidates

- `always_minimax`: accuracy `91.30%`, tokens `3869`, cost `$0.001377`, nondominated `False`.
- `always_kimi`: accuracy `86.96%`, tokens `1685`, cost `$0.002327`, nondominated `True`.
- `intent_policy`: accuracy `91.30%`, tokens `1967`, cost `$0.002191`, nondominated `True`.

## E2B Thresholds

- `0.75`: precision `84.52%`, coverage `12.66%`, Wilson lower `79.54%`.
- `0.80`: precision `84.51%`, coverage `11.35%`, Wilson lower `79.22%`.
- `0.85`: precision `76.32%`, coverage `3.82%`, Wilson lower `65.64%`.

## Gates

- [x] `spend_below_hard_cap`
- [x] `paired_population_complete`
- [x] `selected_no_accuracy_regression`
- [x] `selected_positive_token_savings`
- [x] `bootstrap_lower_bound_positive`
- [x] `selected_is_pareto_nondominated`
- [x] `e2b_threshold_frozen_from_grouped_oof`
- [x] `runtime_models_authorized`

The policy is accuracy-first: token count breaks ties only among candidates with identical deterministic-validator accuracy. Unknown hidden-evaluator behavior remains a stated limitation.
