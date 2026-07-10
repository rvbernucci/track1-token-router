# Submission Notes

## Problem

Track 1 first gates on accuracy and then rewards low Fireworks token usage. Calling the strongest model for every task is accurate but expensive; trusting a small local model everywhere is cheap but unsafe.

## Solution

Track 1 Token Router first offers the untouched task to a fail-closed deterministic solver. Unsupported tasks go to the validation-selected Kimi K2.7 Code model when it is present in `ALLOWED_MODELS`. Strict output validation and allowed-model fallback protect the official response contract.

We also trained FunctionGemma 270M on AMD and evaluated a text-only Gemma 4 E2B route across 2,000 tasks. The local route failed its frozen accuracy gate, so the submission intentionally excludes both models rather than claim unmeasured token savings.

## Why It Can Win

- deterministic tasks are solved without remote calls;
- Kimi achieved the best eligible validation result and 75% binary accuracy on the locked test;
- rejected matrix, per-intent and Minimax policies all used more tokens and/or lost accuracy;
- rejected E2B saved tokens but caused a statistically significant accuracy loss;
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

The frozen championship ablation is complete. The exact Linux `amd64` image is built and resource-gated by CI before release.
