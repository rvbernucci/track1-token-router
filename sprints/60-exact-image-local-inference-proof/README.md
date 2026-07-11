# Sprint 60 - Exact-Image Local Inference Proof

## Objective

Prove that the exact public `v3.2.0-full-hybrid` image performs real FunctionGemma and Gemma E2B inference under the evaluator's `linux/amd64`, 4 GB RAM and 2 vCPU limits. A mock-mode container gate is not sufficient evidence.

## Inputs

- Public image: `ghcr.io/rvbernucci/track1-token-router:v3.2.0-full-hybrid`
- FunctionGemma Q8 SHA-256: `74625dd27cf25d54018fa17328a1b1b43f1f09c179e1e4edfaeeffc0c05d9b77`
- Gemma E2B SHA-256: `181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c`
- Runtime limits: 4 GB RAM, 2 vCPU, 600 seconds, `linux/amd64`

## Work

- [x] Pull the public image after removing all local build state.
- [x] Inspect the image and verify both pinned model files and their hashes.
- [x] Start the container with `--memory=4g --cpus=2 --network=none` for local-only probes.
- [x] Run FunctionGemma assessments and validate the native tool-call schema.
- [x] Select two frozen high-probability E2B probes through the real matrix gate.
- [x] Execute two E2B answers with the 96-token ceiling.
- [x] Pass each candidate through Answer Contract Engine and write official `results.json`.
- [x] Capture sampled container memory, cold start and warm inference latency.
- [x] Verify that no model download or external HTTP request occurs after container start.

## Gates

- [x] Both local model hashes match the pinned values.
- [x] FunctionGemma emits valid assessments with no answer or route fields.
- [x] Both tasks record route `e2b_local`.
- [x] Fireworks prompt and completion tokens are zero for both tasks.
- [x] Sampled peak memory is `728.1 MiB`, below `3584 MiB`.
- [x] Cold inference is `12.560 seconds` and warm inference is `2.627 seconds`.
- [x] Output contains exactly `task_id` and `answer`.

## Evidence

- `reports/public/full-local-exact-image-smoke.json`
- `reports/public/full-local-smoke.md`
- GitHub Actions run `29157770736` retains the full runtime and memory logs.

## Command

```bash
python3 scripts/full_local_image_gate.py \
  --image ghcr.io/rvbernucci/track1-token-router:v3.2.0-full-hybrid \
  --memory 4g --cpus 2 --network none --json
```

## Completion Decision

Passed. GitHub Actions run `29157770736` proved real local inference under the evaluator envelope with zero Fireworks tokens. Promote `v3.2.0-full-hybrid` to Sprint 61 failure-contract testing.
