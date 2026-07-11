# Sprint 35 - Batch Throughput And Timeout Stress

## Type

Does not depend on credits.

## Objective

Stress-test batch execution, timeouts, throughput, and behavior under load using fake providers and a large JSONL, without depending on AMD/Fireworks.

## Why it matters

If the evaluator comes with a large batch or aggressive timeouts, a correct but slow runner might lose. Currently, we have a latency drill; we lack volume stress-testing, partial failures, and time limits per batch.

## Thesis

Competitive performance is not just the p95 of a single task. It is stability under batch loads, partial failures, and deadlines.

## Deliverables

- `scripts/batch_stress.py`.
- `fixtures/stress/`.
- `reports/generated/batch-stress.md`.
- Timeout configuration per environment.
- Tests for large batches, partial failures, and clean JSONL output.
- Optional: controlled concurrent mode for stateless routes.

## Checklist

- [x] Create a JSONL fixture with 1k small synthetic tasks.
- [x] Create a fixture with a mix of easy, formatting, adversarial, and unstable knowledge tasks.
- [x] Simulate a slow local provider.
- [x] Simulate a local provider with intermittent errors.
- [x] Simulate a slow Fireworks provider in dry-run/fake provider.
- [x] Measure throughput in tasks/s.
- [x] Measure total time per batch.
- [x] Measure p50/p95/p99 per task.
- [x] Measure controlled failures versus crashes.
- [x] Validate that JSONL output preserves IDs and order when necessary.
- [x] Validate that stderr can contain diagnostics, but stdout does not clutter the response.
- [x] Define batch thresholds for CI.

## Acceptance criteria

- Stress test runs locally without credits.
- The script fails when timeout/throughput falls outside the envelope.
- Partial failures are recorded without breaking the output contract.
- The report identifies bottlenecks.

## Metrics

- Tasks per second.
- Batch elapsed ms.
- p95/p99 per task.
- Error rate.
- Timeout rate.
- Output contract pass rate.

## Expected commands

```bash
python3 scripts/batch_stress.py --check --report reports/generated/batch-stress.md
python3 -m unittest tests.test_batch_stress
```

## Risks

- Optimizing for throughput and breaking the simplicity of the evaluator.
- Introducing concurrency before proving that the runner is stateless.
- Making the CI run too slowly.

## Decision

The first stress test must be sequential and deterministic. Concurrency will only be introduced if measurements prove it necessary.

## Definition of Done

- Batch stress testing exists.
- Thresholds are configurable.
- The report shows bottlenecks.
- CI remains fast and stable.
