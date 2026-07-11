# Live Three-Route Arena

Decision: `PASS`

- Image: `ghcr.io/rvbernucci/track1-token-router@sha256:6bdf4fcfe5e99181b033a5926208c4e8627fd36e24225c920ae278918ba2ff58`
- Tasks: `96`
- Accuracy: `96.88%`
- Routes: `{"deterministic": 12, "e2b": 12, "fireworks": 72}`
- Remote tokens: `3559`
- Always-Fireworks tokens: `7234`
- Wall time: `242.36s`
- Peak memory: `1140.74 MiB`

## Gates

- [x] `all_three_routes_have_witnesses`
- [x] `output_order_and_ids_match`
- [x] `answer_contract_valid_100pct`
- [x] `runtime_failures_at_most_2pct`
- [x] `batch_within_570_seconds`
- [x] `peak_memory_at_most_3584_mib`
- [x] `authorized_fireworks_only`
- [x] `remote_tokens_below_always_fireworks`
- [x] `raw_prompt_envelope_separation`
- [x] `e2b_failure_falls_through`
- [x] `terminal_remote_failure_nonzero_no_output`
