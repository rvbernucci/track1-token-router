# Track 1 Final Environment Strategy

Updated: 2026-07-13

## Hard Constraints

- Public Docker image with a Linux `amd64` manifest.
- Compressed image below 10 GB.
- 4 GB RAM, 2 vCPU and at most 10 minutes.
- Ready within 60 seconds; each task completes in under 30 seconds.
- All natural-language responses are in English.
- Valid atomic `/output/results.json` and exit code zero on success.
- Only runtime `ALLOWED_MODELS` through `FIREWORKS_BASE_URL`.
- No hardcoded answers, credentials or startup downloads.
- Local inference counts toward accuracy and uses zero scored Fireworks tokens.

## Promoted Candidate

```text
Proof-carrying deterministic solver
-> FunctionGemma assessment for unresolved tasks
-> FunctionGemma planner plus mechanically proven tool execution
-> selective Gemma 4 E2B
-> Kimi by default / MiniMax for logic, sentiment and summarization
-> Answer Contract Engine
```

The current recommended public image is `ghcr.io/rvbernucci/track1-token-router:v3.12.3-proof-pull-retry`. It embeds separate SHA-pinned FunctionGemma assessment and planner Q8 artifacts plus Gemma E2B and requires no model downloads during evaluation. `v3.12.1-no-hardcoded-startup-sla` is the immediate rollback; `v3.7.3-public-sample` remains the officially scored rollback.

## Evaluator Variables

The image contains no `.env` file. The evaluator injects `FIREWORKS_API_KEY`, `FIREWORKS_BASE_URL` and `ALLOWED_MODELS`. The first two configure the tracked API route. `ALLOWED_MODELS` is the hard authorization boundary and overrides every policy preference.

## Resource Proof

- compressed size: 2,938,881,530 bytes;
- exact public-image platform: `linux/amd64`;
- exact published-image release run: `29247825641`;
- clean-pull local-inference peak: 1,299.456 MiB;
- resource gate: 4 GB, 2 vCPU, no network, 600-second ceiling;
- cold-start plus official smoke: 5 seconds, below the 60-second gate;
- absolute Fireworks task deadline: 28 seconds;
- OCI digest: `sha256:ec0d62c4c08489e8b8f06abf26087d1c1bfa43128d330b591f8588976b333c59`.

## Failure Strategy

Every local stage fails closed to an authorized Fireworks model. The system never treats confidence, fluent prose or a regression score as proof. A terminal Fireworks transport failure exits non-zero before writing a synthetic answer as if it were successful.

## Rollback

The immediate rollback is `ghcr.io/rvbernucci/track1-token-router:v3.12.1-no-hardcoded-startup-sla`. The officially scored rollback is `ghcr.io/rvbernucci/track1-token-router:v3.7.3-public-sample`; the compact emergency rollback remains `v2.1.0-proof-router`. Rollback requires changing only the Docker Image field.
