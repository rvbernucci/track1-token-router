# Championship Architecture

Updated: 2026-07-12

## Final Runtime

The promoted image is `ghcr.io/rvbernucci/track1-token-router:v3.7.0-wilson-nash` (`linux/amd64`). It embeds both local models and performs no startup download. `v3.6.0-category-calibrated` remains the verified one-field rollback.

```text
/input/tasks.json
-> engine extracts each untouched prompt
-> FunctionGemma 270M Q8 assessment
-> proof-carrying deterministic solver when uniquely supported
-> category-specific normalized E2B matrix, calibrator and threshold
-> Wilson 90% confidence bound plus deterministic Nash/minimax guard
-> text-only Gemma 4 E2B candidate plus Answer Contract Engine
-> Fireworks Kimi/MiniMax policy on refusal, uncertainty or local failure
-> engine reconstructs atomic /output/results.json
```

The authorization boundary is always the harness-provided `ALLOWED_MODELS`. All remote calls use `FIREWORKS_BASE_URL`; no model ID outside that runtime list can be called.

## Local Assessment

FunctionGemma emits one structured assessment containing an intent and five scores. The matrix was fitted on raw FunctionGemma outputs, so runtime routing deliberately uses the raw assessment rather than its display calibration. Invalid, malformed or timed-out assessments fail closed to Fireworks.

- Artifact: FunctionGemma scale-789 Q8 GGUF
- SHA-256: `74625dd27cf25d54018fa17328a1b1b43f1f09c179e1e4edfaeeffc0c05d9b77`
- Output ceiling: 64 tokens

## Deterministic Route

Registered solvers receive the untouched prompt and release an answer only with a unique, independently recomputable proof. A regression score can propose a solver but cannot override failed proof. Unsupported or ambiguous tasks continue safely.

## Gemma E2B Route

The v2 matrix combines FunctionGemma's five scores with 40 prompt-only mechanical features. It persists fit-only normalization, one ridge model, one Platt calibrator and one threshold per predicted intent. The `6,845`-row ledger includes `2,383` valid expansion assessments; `17` malformed assessments fail closed to Fireworks.

The candidate decision surface was frozen before opening the 480-row expansion holdout. Sentiment alone passed promotion with `44/46` correct (`95.65%` precision, `85.47%` Wilson lower bound). Factual QA and NER were accurate in their selected samples but remained disabled because support was below the frozen minimum. Missing features, unknown intents, non-finite values, contract failures, local errors and insufficient deadline reserve all route to Fireworks.

E2B receives only the original prompt and may generate at most 96 tokens. The engine, not the model, removes safe wrappers and reconstructs the official JSON envelope.

The Wilson-Nash guard is scoped to the exact v2 decision surface. It cannot transfer the `44/46` holdout evidence to a task below the frozen per-intent probability threshold. It records the 90% Wilson lower bound, utility interval, worst-case regret and reason without logging prompt contents. Review is disabled, so the guard can only preserve an eligible E2B route or fail closed to direct Fireworks.

- Artifact: Gemma 4 E2B LiteRT-LM, text-only execution
- SHA-256: `181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c`
- Exact final-image gate: 9.48 s cold, 1.447 s warm, 639.8 MiB sampled container peak
- Exact final-image probes: two `e2b_local` answers and zero Fireworks tokens

## Fireworks Route

The final validation policy is Kimi K2.7 Code by default and MiniMax M3 for NER/extraction. It is a preference, never an authorization override. If the preferred model is absent, the runtime uses only another model present in `ALLOWED_MODELS`.

| Policy | Valid | Tokens |
| --- | ---: | ---: |
| Always MiniMax | 21/23 | 3,869 |
| Always Kimi | 20/23 | 1,685 |
| Final intent policy | 21/23 | 1,967 |

The final policy is nondominated: it matches the strongest deterministic-validator accuracy and saves 1,902 tokens. The paired bootstrap token-savings CI95 is `[1,608, 2,185]`. These tasks are calibration evidence, not a claim about hidden-evaluator accuracy.

## Failure Policy

| Failure | Action |
| --- | --- |
| Deterministic refusal or failed proof | Continue to E2B/Fireworks |
| Invalid FunctionGemma assessment | Fireworks |
| E2B below threshold | Fireworks without E2B inference |
| Wilson-Nash guard rejects matrix probe | Fireworks without E2B inference |
| E2B malformed, timed out or runtime failure | Fireworks with structured fallback reason |
| Preferred remote model not allowed | Select another runtime-authorized model |
| Terminal Fireworks failure | Exit non-zero before publishing synthetic output |
| Deadline reserve reached | Preserve one controlled result per remaining task |

## Delivery Proof

- Promoted image: `v3.7.0-wilson-nash`
- OCI manifest digest: `sha256:3b661e9abf9f491d8f63ee941b218ba8269b6cd82c09d897723167f0c6513620`
- Platform digest: `sha256:cc53eb3cebe712073c28cc9f2f00acd466065fcf9df32a9fe9e8ff39773ae2b2`
- Compressed size: 2,666,352,767 bytes
- Source revision: `2b76451f885ff36e8874f212779a36c7f539e0c0`
- Release run: `29196181749`
- Exact local-inference run: `29196742441`
- Exact local metrics: cold `9.48 s`, warm `1.447 s`, sampled peak `639.8 MiB`, two local routes and zero Fireworks tokens
- Verified one-field rollback image: `v3.6.0-category-calibrated`
- Verified rollback OCI manifest: `sha256:a8f2045a69518b72c7e8c5b9692e82fee8f43891b74dc64c9bdf75b0e2b17221`
- Verified rollback platform digest: `sha256:ff4688aa1f21dacc26a01c676b1b9c4ebd866bc94aa61ac4b22a596d42c8c788`
- Verified rollback compressed size: 2,666,207,512 bytes
- Verified rollback source revision: `1f74aab876ec3c693516284f80bcfc9a3bf92769`
- Verified rollback release and exact-image run: `29171230908`
- Compact rollback: `v2.1.0-proof-router`

## Evidence Boundaries

The 80-row balanced arena is a frozen holdout replay plus exact-image envelope projection, not a live 80-row container run. Historical rejected policies remain in the repository for reproducibility and are explicitly marked as historical. Current release truth is defined by this document, `README.md`, `SUBMISSION.md` and `submission/final/final-release-decision.json`.

Sprints 71-74 are frozen championship evidence. Semantic-v3 Q8, cluster augmentation and verify-or-repair failed their promotion gates and remain outside the runtime. The Wilson-Nash fail-closed guard passed protected replay, is hash-pinned in `v3.7.0-wilson-nash`, and cannot expand the proven v2 E2B cohort.

## Non-Goals

- No LLM judge in the runtime answer path.
- No embeddings, RAG or multimodality.
- No hardcoded or cached answers.
- No API-dollar optimization in place of the official token objective.
