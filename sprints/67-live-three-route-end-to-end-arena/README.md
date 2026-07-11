# Sprint 67 - Live Three-Route End-to-End Arena

## Objective

Execute the exact public image with real local inference and real Fireworks calls, proving deterministic, E2B and remote routes together under the official resource and I/O contract.

## Preflight

- [ ] Pin the exact public image digest, not only its mutable tag.
- [ ] Verify `linux/amd64`, compressed size and OCI revision labels.
- [ ] Inject credentials only through environment variables.
- [ ] Use a temporary input/output directory with no repository secrets.
- [ ] Set 4 GB RAM, 2 vCPU and a 570-second application deadline.
- [ ] Confirm the selected Fireworks models appear in `ALLOWED_MODELS`.

## Dataset

- [ ] Freeze 96 unseen tasks, 12 per Track 1 category.
- [ ] Include expected deterministic, E2B and Fireworks cohorts.
- [ ] Include local refusal and local runtime-failure probes.
- [ ] Keep expected routes advisory; score final correctness independently.
- [ ] Preserve prompt hashes and sealed expected answers.

## Execution

- [ ] Clean-pull the exact image before running.
- [ ] Execute the official `/input/tasks.json` to `/output/results.json` flow.
- [ ] Capture route, fallback reason, model, latency and token usage per task.
- [ ] Measure cold start, total wall time, peak memory and exit code.
- [ ] Verify prompt text, not the JSON envelope, reaches every model.
- [ ] Verify `task_id` never enters an inference prompt.
- [ ] Re-run one deterministic subset with networking disabled.

## Gates

- [ ] All three routes have successful witnesses.
- [ ] Output order and task IDs exactly match input.
- [ ] Answer-contract validity is `100%`.
- [ ] Runtime failures are at most `2%`.
- [ ] Entire batch completes within `570 seconds`.
- [ ] Peak memory is at most `3584 MiB`.
- [ ] Zero unauthorized or untracked Fireworks calls.
- [ ] Remote tokens are below the always-Fireworks replay baseline.
- [ ] Terminal remote failure exits non-zero without publishing synthetic success.

## Evidence

- `evals/live-three-route-v1/tasks.json`
- `submission/final/live-three-route-image-audit.json`
- `reports/generated/live-three-route-v1/results.jsonl`
- `reports/generated/live-three-route-v1/resources.json`
- `reports/public/live-three-route-arena.md`

## Command

```bash
python3 scripts/run_live_three_route_arena.py \
  --image ghcr.io/rvbernucci/track1-token-router:v3.3.0-full-hybrid \
  --memory 4g --cpus 2 --deadline-seconds 570 \
  --check --json
```

## Completion Decision

Retain the current release unless the exact-image live run improves evidence without violating accuracy, resource, authorization or output-contract gates.
