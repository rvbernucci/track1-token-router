# Builder Plan

## North Star

Build the most accurate Track 1 agent that spends the fewest Fireworks tokens after crossing the accuracy gate.

## Active Architecture

```text
FunctionGemma 270M
-> intent + five calibrated scores
-> engine outcome regression matrix
-> accuracy gate + minimax regret
-> deterministic | Gemma 4 E2B | Fireworks Pareto/Nash
```

See [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

## Engineering Principles

- Accuracy gates local token savings.
- FunctionGemma assesses; it does not answer or choose an engine.
- Deterministic solvers independently prove applicability.
- E2B is promoted separately per task family.
- Fireworks model IDs come only from `ALLOWED_MODELS`.
- Self-reported confidence is never a safety boundary.
- Every route has explicit timeout, parse and fallback behavior.
- Metrics include end-to-end accuracy, remote tokens, latency and peak RSS.
- The Docker envelope is tested continuously, not only before submission.

## Current Work

Sprint 45 is complete. Sprint 46 is now in progress; dataset quality gates precede training.

| Sprint | Outcome |
|---|---|
| 45 | Complete: TaskAssessment, score rubrics, feature vectors and engine-outcome contracts promoted |
| 46 | In progress: build the resumable Sonnet 5/Fireworks Dataset Forge, then train and calibrate FunctionGemma |
| 47 | Package E2B and build the empirical task-engine outcome matrix and regressions |
| 48 | Implement accuracy gating, minimax regret and Fireworks Pareto/Nash selection |
| 49 | Ablate direct routing versus regression/game theory and promote the winning image |

## Existing Assets To Reuse

- official adapters and CLI;
- deterministic solver registry;
- Fireworks client and allowed-model enforcement;
- matrix-regression and game-theory selector;
- offline, adversarial and semantic eval sets;
- token, latency, trace and release tooling;
- Docker, CI, GHCR and submission audits.

## Definition Of Done

- FunctionGemma emits one valid calibrated assessment per task.
- Deterministic route cannot force an unsupported answer.
- E2B is local, text-only and bundled without startup downloads.
- Fireworks fallback selects only the cheapest sufficient allowed model.
- `/output/results.json` stays valid on successful runs.
- The final image fits 4 GB RAM, 2 vCPU, 10 minutes and 10 GB compressed.
- Fireworks token reduction is measured against an accuracy-matched champion.

## Anti-Scope

- UI work before the scoring runner is stable;
- multimodality without an evaluator requirement;
- embeddings or RAG without a retrieval corpus;
- large local Gemma checkpoints;
- a second semantic verifier before the basic three-route ablation;
- model-specific shortcuts that violate unseen-variant rules.
