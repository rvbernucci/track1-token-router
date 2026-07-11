# Full Local Eight-Category Arena

Decision: `PASS`

## Results

- Frozen final holdout: `80` rows, 10 per Track 1 category.
- Accuracy: `100.00%`.
- Local precision: `100.00%`; Wilson 95% lower bound `91.24%`.
- Local coverage: `50.00%`.
- Remote tokens: `1145` versus `2676` always-Fireworks.
- Token reduction: `57.21%`.
- Runtime projection: `243.693` seconds with `326.307` seconds reserve.
- Exact-image sampled peak memory: `728.1` MiB.

## Gates

- [x] `lineage_hashes_valid`
- [x] `balanced_eight_categories`
- [x] `deadline_projection_below_570_seconds`
- [x] `peak_memory_at_most_3584_mib`
- [x] `answer_contract_validity_100pct`
- [x] `local_precision_at_least_80pct`
- [x] `runtime_failure_rate_at_most_2pct`
- [x] `all_categories_successful`
- [x] `remote_tokens_below_always_fireworks`

## Evidence Boundary

The 80-row accuracy and token results are a lineage-separated frozen replay. The container timing and memory figures come from the exact public image gate. Runtime is a conservative projection that charges one warm local inference per remaining row plus frozen Fireworks p95 latency; it is not represented as a live 80-row image run.
