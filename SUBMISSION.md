# Submission Notes

## Problem

Track 1 first gates on accuracy and then rewards low Fireworks token usage. Calling the strongest model for every task is accurate but expensive; trusting a small local model everywhere is cheap but unsafe.

## Solution

Track 1 Token Router assesses the untouched task with embedded FunctionGemma 270M, releases proof-carrying deterministic answers when available, and selectively probes embedded Gemma 4 E2B. Remaining tasks use a validation-selected Kimi/MiniMax policy constrained by runtime `ALLOWED_MODELS`. Strict output validation protects the official response contract.

We trained FunctionGemma 270M on AMD and built a `6,845`-row routing ledger. The expansion adds `2,400` E2B answers processed by the production Answer Contract Engine and independently labeled; `824` were correct. The frozen category model promoted sentiment only after a once-opened holdout produced `44/46` correct selected answers (`95.65%` precision; `85.47%` Wilson lower bound). The final image embeds both local models and requires no model download at startup.

## Why It Can Win

- proof-carrying deterministic tasks are solved without remote calls;
- the expanded ordering proof recovered both known correct candidates and rejected all five incorrect candidates;
- a 46-call live Pareto calibration selected Kimi by default and MiniMax for extraction;
- the selected policy matched the strongest 21/23 result while reducing tokens from 3,869 to 1,967;
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

## Evaluator Configuration

No `.env` file is required or included. The harness injects `FIREWORKS_API_KEY`, `FIREWORKS_BASE_URL` and `ALLOWED_MODELS` as container environment variables. The runtime consumes them directly and treats `ALLOWED_MODELS` as the authorization boundary.

## Current Status

The promoted image is `ghcr.io/rvbernucci/track1-token-router:v3.7.0-wilson-nash`; `v3.6.0-category-calibrated` is the one-field rollback and `v2.1.0-proof-router` the compact rollback. Release run `29196181749` and exact local-inference run `29196742441` are green. The public image is 2,666,352,767 compressed bytes and requires no startup downloads.
