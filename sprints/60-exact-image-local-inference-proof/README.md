# Sprint 60 - Exact-Image Local Inference Proof

## Objective

Prove that the exact public `v3.0.0-full-local` image performs real FunctionGemma and Gemma E2B inference under the evaluator's `linux/amd64`, 4 GB RAM and 2 vCPU limits. A mock-mode container gate is not sufficient evidence.

## Inputs

- Public image: `ghcr.io/rvbernucci/track1-token-router:v3.0.0-full-local`
- FunctionGemma Q8 SHA-256: `74625dd27cf25d54018fa17328a1b1b43f1f09c179e1e4edfaeeffc0c05d9b77`
- Gemma E2B SHA-256: `181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c`
- Runtime limits: 4 GB RAM, 2 vCPU, 600 seconds, `linux/amd64`

## Work

- [ ] Pull the public image after removing all local build state.
- [ ] Inspect the image and verify both pinned model files and their hashes.
- [ ] Start the container with `--memory=4g --cpus=2 --network=none` for local-only probes.
- [ ] Run one FunctionGemma assessment and validate the native tool-call schema.
- [ ] Select a frozen high-probability E2B probe through the real matrix gate.
- [ ] Execute one E2B answer with the 96-token ceiling.
- [ ] Pass the candidate through Answer Contract Engine and write official `results.json`.
- [ ] Capture cgroup peak memory, process high-water RSS, cold start and warm inference latency.
- [ ] Verify that no model download or external HTTP request occurs after container start.

## Gates

- [ ] Both local model hashes match the pinned values.
- [ ] FunctionGemma emits one valid assessment with no answer or route fields.
- [ ] At least one task records route `e2b_local` or `e2b_local_repaired`.
- [ ] Fireworks prompt and completion tokens are both zero for the local task.
- [ ] Peak cgroup memory is at most `3584 MiB`.
- [ ] End-to-end local smoke completes within `120 seconds` cold and `30 seconds` warm.
- [ ] Output contains exactly `task_id` and `answer`.

## Evidence

- `reports/generated/full-local/exact-image-smoke.json`
- `reports/generated/full-local/process-memory.jsonl`
- `reports/generated/full-local/results.json`
- `reports/public/full-local-smoke.md`

## Command

```bash
python3 scripts/full_local_image_gate.py \
  --image ghcr.io/rvbernucci/track1-token-router:v3.0.0-full-local \
  --memory 4g --cpus 2 --network none --json
```

## Completion Decision

Promote to Sprint 61 only if real E2B inference passes every gate. Otherwise retain `v2.1.0-proof-router` in the form while repairing the full image.
