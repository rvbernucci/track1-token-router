# Full Local Exact-Image Smoke

## Decision

The final exact public image `ghcr.io/rvbernucci/track1-token-router:v3.3.0-full-hybrid` performed real FunctionGemma assessment and Gemma E2B answer inference without network access or Fireworks tokens.

## Evaluator Envelope

- Platform: `linux/amd64`
- Limits: 4 GB RAM, 2 vCPU, network disabled
- Cold task: 12.147 seconds
- Warm task: 1.825 seconds
- Total wall time: 15.355 seconds
- Sampled peak memory: 727.5 MiB
- Routes: two `e2b_local`
- Fireworks tokens: zero prompt and zero completion tokens
- Output: valid official `results.json`

## Supply-Chain Proof

- FunctionGemma SHA-256: `74625dd27cf25d54018fa17328a1b1b43f1f09c179e1e4edfaeeffc0c05d9b77`
- Gemma E2B SHA-256: `181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c`
- Source artifact SHA-256: `f3b88bf1a44e093fcfe50db30f466b5433509fb1815092ab2d64e3e0c3d605dd`

## Reproduction

The authoritative GitHub Actions run is [Full Local Exact-Image Gate 29158947843](https://github.com/rvbernucci/track1-token-router/actions/runs/29158947843). It clean-pulled the public image, verified both embedded model hashes and executed the probes under the evaluator limits.

```bash
python3 scripts/full_local_image_gate.py \
  --image ghcr.io/rvbernucci/track1-token-router:v3.3.0-full-hybrid \
  --memory 4g --cpus 2 --network none --json
```

The compact machine-readable evidence is `reports/public/full-local-exact-image-smoke.json`. Full runtime and memory logs remain attached to the immutable workflow run.
