# Final Hybrid Scorecard

Decision: `PROMOTE`

- Image: `ghcr.io/rvbernucci/track1-token-router:v3.3.0-full-hybrid`.
- OCI manifest: `sha256:6bcff04a9b5929b3788345d41304e3d6b98a9901116546afb16ae1e9445139ed`.
- Compressed size: `2.666 GB`.
- Exact-image cold/warm: `12.147` / `1.825` seconds.
- Exact-image sampled peak memory: `727.5` MiB.
- Exact-image local probes: two E2B routes, zero Fireworks tokens.
- Fireworks Pareto: `21/23` valid with `1967` tokens.
- MiniMax baseline: `21/23` valid with `3869` tokens.
- E2B OOF threshold: `0.75` at `84.52%` precision.
- Rollback: `ghcr.io/rvbernucci/track1-token-router:v2.1.0-proof-router`.

The promotion is accuracy-first. Claims distinguish live Fireworks calibration, frozen holdout replay and exact-image local inference.
