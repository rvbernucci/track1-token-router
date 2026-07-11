# Sprint 67 - Live Three-Route End-to-End Arena

## Objective

Execute the exact public image with real local inference and real Fireworks calls, proving deterministic, E2B and remote routes together under the official resource and I/O contract.

## Preflight

- [x] Pin exact digest `sha256:6bdf4fcfe5e99181b033a5926208c4e8627fd36e24225c920ae278918ba2ff58`.
- [x] Verify `linux/amd64`, 2,666,205,890 compressed bytes and OCI revision `71303be255bfe45c5d502e463aea9b899cc41c8d`.
- [x] Inject credentials only through inherited environment variables.
- [x] Use temporary input/output directories with no repository secrets.
- [x] Set 4 GB RAM, 2 vCPU and a 570-second application deadline.
- [x] Confirm MiniMax and Kimi in runtime `ALLOWED_MODELS`.

## Dataset

- [x] Freeze 96 unseen tasks, 12 per Track 1 category.
- [x] Include expected deterministic, E2B and Fireworks cohorts.
- [x] Include E2B runtime-failure fallback and terminal remote-failure probes.
- [x] Keep expected routes advisory; score final correctness independently.
- [x] Preserve prompt hashes and sealed mechanical validators.

## Execution

- [x] Clean-pull and gate the exact image in release run `29168714893`.
- [x] Execute the official `/input/tasks.json` to `/output/results.json` flow.
- [x] Capture route, fallback, authorized model, remote latency and token usage per task.
- [x] Measure total wall time (`242.36s`), peak memory (`1140.74 MiB`) and exit code.
- [x] Verify prompt hash, not the JSON envelope, reaches inference.
- [x] Verify `task_id` is absent from every inference prompt.
- [x] Exercise terminal failure with networking disabled; deterministic zero-token witnesses are included in the main run.

## Gates

- [x] All three routes have successful witnesses: 12 deterministic, 12 E2B, 72 Fireworks.
- [x] Output order and task IDs exactly match input.
- [x] Answer-contract validity is `100%`.
- [x] Runtime failures are `0%`.
- [x] Entire batch completes in `242.36 seconds`.
- [x] Peak memory is `1140.74 MiB`.
- [x] Zero unauthorized or untracked Fireworks calls.
- [x] 3,559 remote tokens, below the 7,234-token always-Fireworks replay.
- [x] Terminal remote failure exits non-zero without publishing synthetic success.

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

Status: **complete and promoted for subsequent testing**.

The exact public `v3.4.2-full-hybrid` image passed every live gate at `96.88%` mechanical accuracy. The hybrid saved `50.80%` of Fireworks tokens against the same-prompt always-Kimi replay, remained well below time and memory ceilings, and demonstrated both recoverable E2B failure and terminal Fireworks failure behavior. Evidence is frozen in `submission/final/live-three-route-image-audit.json` and `reports/public/live-three-route-arena.md`.
