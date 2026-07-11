# Sprint 15 - Trace Analytics

## Type

Does not depend on credits.

## Objective

Convert JSONL logs into routing, latency, tokens, errors, and regression reports to calibrate the router.

## Deliverables

- Module `router/analytics/traces.py`.
- Script `scripts/analyze_traces.py`.
- Markdown and JSON report.
- Log fixtures.
- Aggregation tests.
- Optional integration into the release check.

## Checklist

- [x] Read `logs/*.jsonl`.
- [x] Aggregate by route.
- [x] Aggregate remote tokens.
- [x] Aggregate latency by stage.
- [x] Count errors and parse failures.
- [x] Detect empty run.
- [x] Generate Markdown report.
- [x] Generate JSON.
- [x] Add log fixtures.
- [x] Add tests.

## Acceptance criteria

- A JSONL log turns into a useful report.
- The script tolerates missing/empty files.
- The report helps calibrate policy and prompt.
- Does not require credentials.

## Expected output

An operational lens to understand how the router is behaving.

## Local evidence

```bash
python3 scripts/analyze_traces.py --logs fixtures/logs/sample-run.jsonl
python3 -m unittest tests.test_trace_analytics
scripts/offline_release_check.sh
```

## Decision

The script tolerates empty or missing `logs/*.jsonl`, because actual logs are local artifacts ignored by Git. The release check uses `fixtures/logs/sample-run.jsonl` to validate reproducible behavior.
