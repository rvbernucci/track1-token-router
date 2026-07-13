# Final Hybrid Scorecard

Decision: `PROMOTE`

- Image: `ghcr.io/rvbernucci/track1-token-router:v3.10.1-s80-championship`.
- OCI manifest: `sha256:876b2b91eeca0ddd6c35c6980425ee288bdf091183a39dd6513da1ca04d2bbf4`.
- Compressed size: `2.939 GB`.
- Exact-image cold/warm: `16.221` / `1.461` seconds.
- Exact-image sampled peak memory: `1299.456` MiB.
- Exact-image local probes: two E2B routes, zero Fireworks tokens.
- Fireworks Pareto: `21/23` valid with `1967` tokens.
- MiniMax baseline: `21/23` valid with `3869` tokens.
- E2B OOF threshold: `0.75` at `84.52%` precision.
- Sprint 80 E2B addition: `13/13` protected code-debugging releases; combined protected precision `93/100`.
- Fireworks policy: Kimi by default, MiniMax for the statistically supported logic-puzzle cohort.
- Truncation guard: one accounted retry only with explicit length or incomplete-output evidence.
- Rollback: `ghcr.io/rvbernucci/track1-token-router:v3.9.0-dual-functiongemma`.

The promotion is accuracy-first. Claims distinguish live Fireworks calibration, frozen holdout replay and exact-image local inference.
