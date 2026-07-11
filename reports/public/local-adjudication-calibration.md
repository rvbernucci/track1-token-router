# Local Adjudication Calibration

- promoted: `False`
- fresh holdout releases: `42`
- fresh holdout precision: `100.00%`
- Wilson lower 95%: `91.62%`
- fresh holdout coverage: `40.38%`
- false local releases: `0`
- Brier score: `0.0004`
- expected calibration error: `0.0163`
- p95 evidence latency: `25.03 ms`

## Gates

- [x] `fresh_holdout_declared`
- [x] `split_groups_disjoint`
- [x] `holdout_not_used_for_model_or_threshold_selection`
- [x] `minimum_20_development_lineages_per_enabled_family`
- [x] `minimum_holdout_releases`
- [x] `holdout_precision_at_least_85_percent`
- [x] `holdout_wilson_at_least_75_percent`
- [x] `zero_verifier_invalid_releases`
- [x] `zero_false_local_releases`
- [x] `factual_open_world_always_remote`
- [ ] `perturbation_flip_rate_below_5_percent`
- [x] `p95_adjudication_below_100_ms`

## Model Selection

Selected `logistic_linear` after comparing constant, linear logistic, nonlinear logistic and monotonic calibrated variants on validation only.
Thresholds maximize Wilson lower precision before coverage. The fresh holdout is used only for the final promotion decision.

## Runtime Contract

A local answer is released only when the E2B candidate satisfies Answer Contract v2, a registered verifier accepts it, the post model clears its cohort threshold and distribution drift remains inside the calibrated envelope. Every failure routes to Fireworks; factual open-world tasks remain remote.
