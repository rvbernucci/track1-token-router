# Trace Summary

- records: 3
- empty_run: `False`
- errors: 1
- parse_failures: 1
- remote_tokens: `{"completion": 40, "prompt": 240, "total": 280}`
- latency_ms: `{"latency_fireworks_ms": 95, "latency_m1_ms": 32, "latency_m2a_ms": 48, "latency_m2b_ms": 40}`
- budget: `{"decisions": {"allow_remote": 1}, "denials": 0}`

## Routes

| route | count |
|---|---:|
| fireworks_replaced | 1 |
| local_error | 1 |
| m1_approved | 1 |

## Interpretation

- Route distribution shows whether policy is drifting toward local or remote paths.
- Remote token totals show budget pressure before real Fireworks calibration.
- Parse failures and error routes are release blockers if they grow in offline runs.
