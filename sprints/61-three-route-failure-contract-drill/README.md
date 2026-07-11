# Sprint 61 - Three-Route Failure And Contract Drill

## Objective

Exercise deterministic, Gemma E2B and Fireworks routes in the exact image, then prove that every local failure fails closed to an evaluator-authorized Fireworks model without corrupting the official output contract.

## Test Matrix

- [ ] Deterministic unique proof releases a zero-token answer.
- [ ] Deterministic ambiguity refuses and continues safely.
- [ ] FunctionGemma valid assessment reaches matrix selection.
- [ ] FunctionGemma malformed output routes directly to Fireworks.
- [ ] Matrix probability below threshold avoids E2B inference.
- [ ] Matrix probability at or above threshold probes E2B.
- [ ] E2B valid candidate is normalized and released.
- [ ] E2B truncation, timeout and malformed output fall through to Fireworks.
- [ ] Unknown or reordered `ALLOWED_MODELS` never causes an unauthorized call.
- [ ] Fireworks timeout produces a non-zero process exit without malformed JSON.

## Contract Checks

- [ ] `/input/tasks.json` is never sent as a model prompt.
- [ ] Models receive only the untouched task text plus their minimal role-specific protocol.
- [ ] `task_id` remains engine-owned and byte-identical.
- [ ] `/output/results.json` is atomic, valid JSON and preserves input order.
- [ ] Logs never contain API keys, authorization headers or sealed references.
- [ ] Every fallback reason is represented in structured routing telemetry.

## Gates

- [ ] Three successful route witnesses exist: deterministic, E2B and Fireworks.
- [ ] Zero unauthorized Fireworks model calls.
- [ ] Zero local-runtime errors released as answers.
- [ ] Zero malformed output rows across success and failure drills.
- [ ] Failure injection adds no more than one remote request per task.

## Evidence

- `reports/generated/full-local/three-route-ledger.jsonl`
- `reports/generated/full-local/failure-injection.json`
- `reports/public/three-route-contract-drill.md`

## Command

```bash
python3 scripts/three_route_container_drill.py \
  --image ghcr.io/rvbernucci/track1-token-router:v3.0.0-full-local \
  --fixtures fixtures/full-local/three-route --json
```

## Completion Decision

Any false local release, unauthorized model call or malformed result blocks the full image from submission.
