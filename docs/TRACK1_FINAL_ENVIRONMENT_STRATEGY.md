# Track 1 Final Environment Strategy

Updated: 2026-07-11

## Hard Constraints

- Public Docker image with a Linux `amd64` manifest.
- Compressed image below 10 GB.
- 4 GB RAM, 2 vCPU and at most 10 minutes.
- Valid atomic `/output/results.json` and exit code zero on success.
- Only runtime `ALLOWED_MODELS` through `FIREWORKS_BASE_URL`.
- No hardcoded answers, credentials or startup downloads.
- Local inference counts toward accuracy and uses zero scored Fireworks tokens.

## Promoted Candidate

```text
FunctionGemma assessment
-> proof-carrying deterministic solver
-> selective Gemma 4 E2B
-> Kimi by default / MiniMax for logic, sentiment and summarization
-> Answer Contract Engine
```

The current recommended public image is `ghcr.io/rvbernucci/track1-token-router:v3.8.2-e2b-contract`. It embeds the SHA-pinned FunctionGemma Q8 and Gemma E2B artifacts and requires no model downloads during evaluation. `v3.7.3-public-sample` remains the officially scored rollback.

## Evaluator Variables

The image contains no `.env` file. The evaluator injects `FIREWORKS_API_KEY`, `FIREWORKS_BASE_URL` and `ALLOWED_MODELS`. The first two configure the tracked API route. `ALLOWED_MODELS` is the hard authorization boundary and overrides every policy preference.

## Resource Proof

- compressed size: 2,666,356,424 bytes;
- exact public-image platform: `linux/amd64`;
- exact published-image release run: `29204166556`;
- sampled resource-gate process peak: 28.645 MiB;
- resource gate: 4 GB, 2 vCPU, no network, 600-second ceiling.

## Failure Strategy

Every local stage fails closed to an authorized Fireworks model. The system never treats confidence, fluent prose or a regression score as proof. A terminal Fireworks transport failure exits non-zero before writing a synthetic answer as if it were successful.

## Rollback

The officially scored rollback is `ghcr.io/rvbernucci/track1-token-router:v3.7.3-public-sample`. The compact emergency rollback remains `ghcr.io/rvbernucci/track1-token-router:v2.1.0-proof-router`. Rollback requires changing only the Docker Image field in the submission form.
