# Final Hybrid Scorecard

Decision: `PROMOTE`

- Image: `ghcr.io/rvbernucci/track1-token-router:v3.9.0-dual-functiongemma`.
- OCI manifest: `sha256:86d9661ccff0fc181feb46fe517816f2bbb18b47e6fe4ee1a6aeb45f4575b363`.
- Compressed size: `2.939 GB`.
- Exact-image cold/warm: `16.221` / `1.461` seconds.
- Exact-image sampled peak memory: `1299.456` MiB.
- Exact-image local probes: two E2B routes, zero Fireworks tokens.
- Fireworks Pareto: `21/23` valid with `1967` tokens.
- MiniMax baseline: `21/23` valid with `3869` tokens.
- E2B OOF threshold: `0.75` at `84.52%` precision.
- Rollback: `ghcr.io/rvbernucci/track1-token-router:v3.8.2-e2b-contract`.

The promotion is accuracy-first. Claims distinguish live Fireworks calibration, frozen holdout replay and exact-image local inference.
