# Submission Notes

## Problem

Track 1 first gates on accuracy and then rewards low Fireworks token usage. Calling the strongest model for every task is accurate but expensive; trusting a small local model everywhere is cheap but unsafe.

## Solution

Track 1 Token Router first offers the untouched task to a fail-closed deterministic solver. Unsupported tasks go to the validation-selected Kimi K2.7 Code model when it is present in `ALLOWED_MODELS`. Strict output validation and allowed-model fallback protect the official response contract.

We also trained FunctionGemma 270M on AMD and evaluated a text-only Gemma 4 E2B route across 2,000 post-contract answers. E2B answered 828 correctly. Of the 1,991 tasks with valid 270M parameters, an intent-specific regression selected 252 at 84.52% out-of-fold precision and 12.66% coverage. The zero-download release excludes the 2.59 GB model artifact unless it is explicitly bundled at image-build time.

## Why It Can Win

- proof-carrying deterministic tasks are solved without remote calls;
- the expanded ordering proof recovered both known correct candidates and rejected all five incorrect candidates;
- Kimi achieved the best eligible validation result and 75% binary accuracy on the locked test;
- rejected matrix, per-intent and Minimax policies all used more tokens and/or lost accuracy;
- the optional E2B frontier identifies a measured high-value local cohort instead of routing all tasks locally;
- every decision is traceable and evaluator-safe.

## Reproduce

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python3 -m unittest discover -s tests
scripts/offline_release_check.sh
```

## Delivery Gates

- public `linux/amd64` image;
- compressed image below 10 GB;
- 4 GB RAM and 2 vCPU;
- complete run below 10 minutes;
- valid `/output/results.json`;
- no startup downloads or embedded secrets;
- only allowed Fireworks models.

## Current Status

The release image is `ghcr.io/rvbernucci/track1-token-router:v2.1.0-proof-router`. The release workflow blocks publication unless the image passes CI, public pullability, manifest inspection and the exact 4 GB/2 vCPU/no-network resource gate.
