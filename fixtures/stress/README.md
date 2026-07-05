# Stress Fixtures

These fixtures support Sprint 35 batch and timeout stress tests.

- `batch-1k.jsonl`: generated deterministic 1,000-task batch for throughput and ordering checks.
- `mixed.jsonl`: small mixed batch for CLI stdout/stderr and output contract checks.

The stress harness stays sequential by default. Concurrency should only be added after measurements prove it is needed.
