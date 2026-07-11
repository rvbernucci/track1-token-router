# Sprint 61 - Three-Route Failure And Contract Drill

## Objective

Exercise deterministic, Gemma E2B and Fireworks routes in the exact image, then prove that every local failure fails closed to an evaluator-authorized Fireworks model without corrupting the official output contract.

## Test Matrix

- [x] Deterministic unique proof releases a zero-token answer.
- [x] Deterministic ambiguity refuses and continues safely.
- [x] FunctionGemma valid assessment reaches matrix selection.
- [x] FunctionGemma malformed output routes directly to Fireworks.
- [x] Matrix probability below threshold avoids E2B inference.
- [x] Matrix probability at or above threshold probes E2B.
- [x] E2B valid candidate is normalized and released.
- [x] E2B runtime failure and malformed output fall through to Fireworks.
- [x] Unknown or reordered `ALLOWED_MODELS` never causes an unauthorized call.
- [x] Fireworks timeout produces a non-zero process exit without malformed JSON.

## Contract Checks

- [x] `/input/tasks.json` is never sent as a model prompt.
- [x] Models receive only the untouched task text plus their minimal role-specific protocol.
- [x] `task_id` remains engine-owned and byte-identical.
- [x] `/output/results.json` is atomic, valid JSON and preserves input order.
- [x] Logs never contain API keys, authorization headers or sealed references.
- [x] Every local fallback reason is represented in structured routing telemetry.

## Gates

- [x] Three successful route witnesses exist: deterministic, E2B and Fireworks.
- [x] Zero unauthorized Fireworks model calls.
- [x] Zero local-runtime errors released as answers.
- [x] Zero malformed output rows across success and failure drills.
- [x] Timeout failure injection adds no more than one remote request per task.

## Evidence

- `reports/generated/full-local/three-route-ledger.jsonl`
- `reports/generated/full-local/failure-injection.json`
- `reports/public/three-route-contract-drill.md`

## Command

```bash
python3 scripts/three_route_container_drill.py \
  --image ghcr.io/rvbernucci/track1-token-router:v3.2.0-full-hybrid \
  --fixtures fixtures/full-local/three-route --json
```

## Completion Decision

Passed. The drill proves all three routes, dynamic model authorization and fail-closed local behavior. A terminal Fireworks failure now exits non-zero before publishing output. Promote to Sprint 62.
