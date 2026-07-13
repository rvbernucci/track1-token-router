# Championship Architecture

Updated: 2026-07-13

## Final Runtime

The current recommended image is `ghcr.io/rvbernucci/track1-token-router:v3.9.0-dual-functiongemma` (`linux/amd64`). It embeds three local artifacts and performs no startup download. `v3.8.2-e2b-contract` is the immediate rollback and `v3.7.3-public-sample` remains the officially scored rollback.

```text
/input/tasks.json
-> engine extracts each untouched prompt
-> FunctionGemma 270M Q8 assessment
-> proof-carrying deterministic solver when uniquely supported
-> narrow structural tool prefilter
-> independent FunctionGemma 270M Q8 planner
-> allowlisted tool plus deterministic provenance validation and recomputable proof
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

## FunctionGemma Tool Route

A narrow structural prefilter may invoke an independently fine-tuned FunctionGemma planner. The planner cannot release prose or authorize itself: its allowlisted tool name, arguments, numeric provenance, semantic roles and execution result are validated mechanically. Any decline, malformed plan, invalid proof or contract failure falls directly to Fireworks.

- Artifact: FunctionGemma tool planner Q8 GGUF
- SHA-256: `ec412795782acd3ed836ac35e058099bfdb1c3218a1ee86aef32905377dbddaf`
- Output ceiling: 160 tokens
- Sealed evidence: 198/198 released answers correct; 50/50 controls declined
- AMD eight-worker replay: 1,393/1,393 released answers correct; zero unsafe controls

## Gemma E2B Route

The v2 matrix combines FunctionGemma's five scores with 40 prompt-only mechanical features. It persists fit-only normalization, one ridge model, one Platt calibrator and one threshold per predicted intent. The `6,845`-row ledger includes `2,383` valid expansion assessments; `17` malformed assessments fail closed to Fireworks.

The candidate decision surface was frozen before opening the 480-row expansion holdout. Sentiment alone passed promotion with `44/46` correct (`95.65%` precision, `85.47%` Wilson lower bound). Factual QA and NER were accurate in their selected samples but remained disabled because support was below the frozen minimum. Missing features, unknown intents, non-finite values, contract failures, local errors and insufficient deadline reserve all route to Fireworks.

E2B receives only the original prompt and may generate at most 96 tokens. The engine, not the model, removes safe wrappers and reconstructs the official JSON envelope.

The Wilson-Nash guard is scoped to the exact v2 decision surface. It cannot transfer the `44/46` holdout evidence to a task below the frozen per-intent probability threshold. It records the 90% Wilson lower bound, utility interval, worst-case regret and reason without logging prompt contents. Review is disabled, so the guard can only preserve an eligible E2B route or fail closed to direct Fireworks.

- Artifact: Gemma 4 E2B LiteRT-LM, text-only execution
- SHA-256: `181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c`
- Exact final-image gate: 9.737 s cold, 1.596 s warm, 745.7 MiB sampled container peak
- Exact final-image probes: two `e2b_local` answers and zero Fireworks tokens

## Fireworks Route

The current validation policy is Kimi K2.7 Code by default and MiniMax M3 for logic puzzles, sentiment and summarization. It is a preference, never an authorization override. If the preferred model is absent, the runtime uses only another model present in `ALLOWED_MODELS`.

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
| Tool planner decline, malformed plan or failed proof | Fireworks |
| E2B below threshold | Fireworks without E2B inference |
| Wilson-Nash guard rejects matrix probe | Fireworks without E2B inference |
| E2B malformed, timed out or runtime failure | Fireworks with structured fallback reason |
| Preferred remote model not allowed | Select another runtime-authorized model |
| Terminal Fireworks failure | Exit non-zero before publishing synthetic output |
| Deadline reserve reached | Preserve one controlled result per remaining task |

## Delivery Proof

- Recommended image: `v3.9.0-dual-functiongemma`
- OCI manifest digest: `sha256:86d9661ccff0fc181feb46fe517816f2bbb18b47e6fe4ee1a6aeb45f4575b363`
- Platform digest: `sha256:2df039de3ae7a4c89acb8318f70e1bc68db25fb5ec6a613101fc1cad653dc5e4`
- Compressed size: 2,938,728,348 bytes
- Source revision: `84f6d3fdc9d658508731bcca055219070842a100`
- Release and exact published-image gate: `29220259103`
- Clean-pull local inference: 16.221 s cold, 1.461 s warm, 1,299.456 MiB sampled peak
- Officially scored rollback image: `v3.7.3-public-sample` (84.2% accuracy, 4,198 Fireworks tokens)
- Compact rollback: `v2.1.0-proof-router`

## Evidence Boundaries

The 80-row balanced arena is a frozen holdout replay plus exact-image envelope projection, not a live 80-row container run. Historical rejected policies remain in the repository for reproducibility and are explicitly marked as historical. Current release truth is defined by this document, `README.md`, `SUBMISSION.md` and `submission/final/final-release-decision.json`.

Sprints 71-77 are frozen championship evidence. Semantic-v3 Q8, cluster augmentation, verify-or-repair and both Router ML v3 neural challengers failed their promotion gates and remain outside the runtime. The Wilson-Nash E2B guard remains hash-pinned and cannot expand the proven v2 E2B cohort. Sprint 79 adds only the independently proven tool route; unrelated E2B and Fireworks decisions remain unchanged.

## Non-Goals

- No LLM judge in the runtime answer path.
- No embeddings, RAG or multimodality.
- No hardcoded or cached answers.
- No API-dollar optimization in place of the official token objective.
