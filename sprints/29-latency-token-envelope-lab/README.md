# Sprint 29 - Latency And Token Envelope Lab

## Type

Does not depend on credit.

## Objective

Create offline laboratories to measure latency, timeout, cold start, JSONL throughput, and conservative remote token exposure.

## Why It Matters

A correct answer can still lose if it is slow, unstable, or expensive. Before we have real AMD/Fireworks, we can still measure the runner's operational envelope, simulate delays, and detect routes that tend to exceed the budget.

## Thesis

The battle drill must evolve from "is it ready?" to "is it ready within a time and token envelope?".

## Deliverables

- `scripts/latency_drill.py`.
- `scripts/token_envelope.py`.
- `reports/generated/latency-report.md`.
- `reports/generated/token-envelope.md`.
- Readiness integration in the battle drill.
- p95 tests, simulated timeout, and ranking of expensive prompts.

## Checklist

- [x] Measure CLI `ask` cold start.
- [x] Measure time per task in `ROUTER_MODE=competition`.
- [x] Measure time per JSONL batch.
- [x] Measure p50, p95, and p99.
- [x] Simulate slow local provider.
- [x] Simulate slow Fireworks.
- [x] Simulate local timeout.
- [x] Simulate remote timeout.
- [x] Create configurable thresholds per env.
- [x] Fail in `--check` when p95 exceeds limit.
- [x] Calculate estimated tokens per remote packet.
- [x] Calculate worst case per route.
- [x] Generate top 20 most expensive tasks.
- [x] Show remote exposure per policy.
- [x] Integrate `latency_ready` into the battle drill.
- [x] Integrate `token_envelope_ready` into the battle drill.

## Acceptance Criteria

- `latency_drill.py --check` passes in the local environment.
- `token_envelope.py --check` passes without Fireworks.
- Reports show limits, results, and risks.
- Battle drill includes latency and token envelope readiness.
- No measurement depends on real credit.

## Metrics

- CLI cold start.
- p50/p95/p99 per task.
- JSONL tasks throughput per second.
- average and maximum packet tokens.
- remote token exposure per policy.
- number of tasks above budget per task.

## Expected Commands

```bash
python3 scripts/latency_drill.py --check --report reports/generated/latency-report.md
python3 scripts/token_envelope.py --check --report reports/generated/token-envelope.md
python3 scripts/battle_drill.py
```

## Risks

- Confusing offline latency with real GPU latency.
- Creating impossible thresholds for CI.
- Optimizing local cold start and forgetting batch/evaluator.

## Decision

The sprint measures envelopes and trends. Real AMD/Fireworks benchmarks continue on the credit-dependent track.

## Definition of Done

- Latency drill exists and has `--check`.
- Token envelope exists and has `--check`.
- Reports are generated.
- Battle drill consumes the signals.
- CI remains stable.

## Evidence

- `scripts/latency_drill.py --check` measures cold start, individual tasks, JSONL batch, p50/p95/p99, and timeout probes.
- `scripts/token_envelope.py --check` calculates remote exposure per policy, worst case per route, and top 20 most expensive tasks.
- `router/evals/operational_envelope.py` centralizes thresholds and calculations for scripts and battle drill.
- `tests/test_operational_envelope.py` covers percentiles, failure by p95, and token thresholds.
- `tests/test_battle_drill.py` validates `latency_ready` and `token_envelope_ready`.
- `scripts/offline_release_check.sh` executes both labs before the battle drill.
