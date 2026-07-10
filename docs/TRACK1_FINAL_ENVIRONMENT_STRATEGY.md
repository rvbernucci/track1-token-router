# Track 1 Final Environment Strategy

## Hard Constraints

- Docker image publicly pullable with Linux `amd64` manifest.
- Compressed image no larger than 10 GB.
- 4 GB RAM and 2 vCPU grading environment.
- Maximum total runtime 10 minutes.
- Valid `/output/results.json` and exit code 0 on success.
- Only `ALLOWED_MODELS` through `FIREWORKS_BASE_URL`.
- No hardcoded or cached answers.
- Local inference counts toward accuracy and contributes zero Fireworks tokens.

## Promoted Candidate

```text
registered deterministic solver registry
+ validation-selected Kimi when allowed
+ allowed-model fallback ordering
+ strict final validation
```

FunctionGemma plus E2B was the measured challenger, not the promoted image. E2B failed the frozen accuracy gate, so neither local model is bundled. This avoids adding local artifacts that produce no approved zero-token route.

## Resource Policy

- bundle no rejected local model artifact;
- perform no startup download;
- run under the exact 2-vCPU/4-GB container limits;
- reserve time to write valid output before the 10-minute deadline.

## Champion And Challenger

Champion: deterministic fail-closed solvers followed by Kimi when allowed.

Rejected challengers: matrix model selection, per-intent routing, FunctionGemma plus E2B, and Minimax-only.

The full challenger remains available for research, but it cannot replace the champion without a new frozen dataset and promotion gate.

## Failure Strategy

Every local failure routes to Fireworks while the deadline budget permits. The system never treats model confidence, fluent prose or a router prediction as proof of correctness.
