# Submission Notes

## Problem

Track 1 rewards a routing agent that preserves answer quality while minimizing remote token usage.

The hard part is not calling the strongest model. The hard part is knowing when not to call it.

## Solution

`track1-token-router` is a CLI-first runner with a local-first cascade:

- M1 generates a free-form candidate answer locally.
- M2A verifies the candidate locally and emits a compact `approve/escalate` JSON decision.
- If M2A approves, the system returns M1 directly with zero remote tokens.
- If M2A escalates, M2B generates a repaired local answer.
- Fireworks audits only the escalated M2B answer and either approves it or replaces it.

## Token Efficiency Strategy

- Local model calls are used as the default path.
- Remote tokens are spent only after local verification detects risk.
- The Fireworks prompt is compact: original task, M1 candidate, M2B alternative and local concern.
- Fireworks output is constrained to `approve` or `replace`, so completion tokens stay small.
- Logs record route, token usage, latency and parse failures for calibration.

## Why This Can Win

The architecture creates a Pareto search:

- easy tasks exit locally;
- medium tasks get local repair;
- risky tasks get remote validation;
- remote calls stay short because Fireworks audits curated candidates instead of solving from scratch by default.

## Known Limits

- The public golden set is only a calibration harness, not the official scoring distribution.
- Exact-match eval is intentionally simple and should be replaced or extended if the official evaluator exposes richer scoring.
- Local model quality and latency depend on the AMD Developer Cloud runtime and selected model.
- If M2A escalates too often, remote token usage rises; if it approves too often, accuracy may drop.

## Reproduce

```bash
python3 -m pip install -e .
scripts/offline_release_check.sh
```

## Submission Kit

Base lablab artifacts live in [`submission/`](./submission):

- project title;
- short and long descriptions;
- tags;
- video script;
- slides outline;
- CLI demo plan;
- cover image brief.

Validate them with:

```bash
python3 scripts/submission_readiness_check.py
```

## Offline Release Candidate

This repository has a no-credit release path. It can be tested without AMD Developer Cloud or Fireworks:

- offline dataset with 160 tasks;
- policy comparison for `aggressive`, `balanced`, and `conservative`;
- fake OpenAI-compatible providers for local and Fireworks simulation;
- official adapter templates for kickoff format changes;
- secret scan and CI gate.

Credit activation is documented in [`CREDIT_ACTIVATION.md`](./CREDIT_ACTIVATION.md).

## Docker

```bash
docker build -t track1-token-router .
docker run --rm track1-token-router --help
docker run --rm track1-token-router ask "What is 2+2?"
```

## Final Container Artifact

Current public `linux/amd64` release candidate:

```text
ghcr.io/rvbernucci/track1-token-router:offline-rc-20260709-1458
```

Verify without local Docker:

```bash
python3 scripts/competition_submission_audit.py \
  --image ghcr.io/rvbernucci/track1-token-router:offline-rc-20260709-1458 \
  --expected-revision 5bdcf45da70b93473e52677715bc8e5f4ca25a4e \
  --expected-version offline-rc-20260709-1458
```

The audit confirms public pullability, official adapter smoke, deterministic zero-token coverage, `linux/amd64`, the 10GB image limit, and OCI source/revision/version labels.

## Hybrid Run

```bash
docker run --rm \
  -e ROUTER_MODE=hybrid \
  -e LOCAL_BASE_URL=http://host.docker.internal:8000/v1 \
  -e LOCAL_MODEL=local-model \
  -e FIREWORKS_API_KEY="$FIREWORKS_API_KEY" \
  -e FIREWORKS_MODEL=accounts/fireworks/models/replace-me \
  track1-token-router ask "What is 2+2?"
```

## Short Pitch

This project treats token efficiency as a routing problem, not a single prompt problem. It uses local generation, local verification and local repair to avoid unnecessary remote calls, then uses Fireworks as a compact auditor only when local confidence breaks. The result is a reproducible CLI runner designed to trade remote tokens for accuracy only when the trade is worth it.
