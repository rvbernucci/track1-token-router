# Three-Route Failure And Contract Drill

Decision: `PASS`

Exact image: `ghcr.io/rvbernucci/track1-token-router:v3.2.0-full-hybrid`

## Route Witnesses

- Deterministic: proof-carrying arithmetic, zero remote requests.
- Gemma E2B: exact-image local inference inherited from Sprint 60, zero Fireworks tokens.
- Fireworks: raw task text sent to an authorized runtime model and returned through the official adapter.

## Checks

- [x] `exact_image_e2b_witness`
- [x] `exact_image_zero_remote_tokens`
- [x] `named_failure_contract_tests`
- [x] `deterministic_witness`
- [x] `fireworks_witness`
- [x] `remote_failure_nonzero_without_output`
- [x] `dynamic_allowed_model_enforcement`

## Failure Contract

FunctionGemma and E2B failures fall through to Fireworks with structured reasons. A terminal Fireworks failure now makes `submit-track1` exit non-zero before writing `results.json`; it cannot be scored as a synthetic answer.

The drill uses named, deterministic tests for failure injection and the immutable exact-image artifact from GitHub Actions run 29157770736 for real local inference.
