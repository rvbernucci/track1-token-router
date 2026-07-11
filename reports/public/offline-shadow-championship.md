# Offline Shadow Championship

- offline gate: `True`
- release ready: `False`
- selected runtime: `deterministic_fireworks`
- local E2B enabled: `False`
- Docker live gate: `False`
- final holdout rows: `80`

## Ablations

| Variant | Accuracy | Fireworks tokens | Local coverage | Local precision | Simulated latency |
|---|---:|---:|---:|---:|---:|
| fireworks_only | 100.00% | 2676 | 0.00% | 100.00% | 35.68s |
| deterministic_fireworks | 100.00% | 1145 | 50.00% | 100.00% | 17.92s |
| e2b_regression_without_proofs | 76.25% | 429 | 82.50% | 71.21% | 172.59s |
| proof_plus_e2b_cross_validation | 100.00% | 549 | 76.25% | 100.00% | 91.61s |
| full_cohort_binary_adjudication | 100.00% | 1145 | 50.00% | 100.00% | 17.92s |

## Offline Gates

- [x] `hashes_and_splits_valid`
- [x] `all_eight_categories_present`
- [x] `selected_accuracy_gate`
- [x] `no_material_accuracy_regression`
- [x] `fireworks_tokens_reduced`
- [x] `local_precision_gate`
- [x] `runtime_below_shadow_limit`
- [x] `memory_below_shadow_limit`
- [x] `output_schema_valid`
- [x] `chaos_suite_passed`
- [x] `official_io_contract_passed`

## Docker Gap

- static gate: `True`
- live gate executed: `False`
- reason: Docker CLI is unavailable on this Mac; scripts/docker_resource_gate.sh must run in CI/AMD before release.

## Decision

Offline deterministic+Fireworks shadow passed; release remains blocked until Docker live gate and a stable local-E2B policy pass.
No submission attempt is authorized by this report. The exact `linux/amd64` resource rehearsal and a stable local-E2B policy remain mandatory.
