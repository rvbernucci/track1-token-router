# Championship Architecture

Updated: 2026-07-11

## Final Runtime

The promoted image is `ghcr.io/rvbernucci/track1-token-router:v3.3.0-full-hybrid` (`linux/amd64`). It embeds both local models and performs no startup download.

```text
/input/tasks.json
-> engine extracts each untouched prompt
-> FunctionGemma 270M Q8 assessment
-> proof-carrying deterministic solver when uniquely supported
-> per-intent E2B matrix gate at threshold 0.75
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

The per-intent five-score matrix uses the frozen grouped out-of-fold threshold `0.75`. Its development evidence selected 252 of 1,991 valid rows at 84.52% precision and 12.66% coverage; the Wilson 95% lower bound was 79.54%. Invalid assessments and runtime failures route to Fireworks.

E2B receives only the original prompt and may generate at most 96 tokens. The engine, not the model, removes safe wrappers and reconstructs the official JSON envelope.

- Artifact: Gemma 4 E2B LiteRT-LM, text-only execution
- SHA-256: `181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c`
- Exact final-image gate: 12.147 s cold, 1.825 s warm, 727.5 MiB sampled container peak
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
| E2B malformed, timed out or runtime failure | Fireworks with structured fallback reason |
| Preferred remote model not allowed | Select another runtime-authorized model |
| Terminal Fireworks failure | Exit non-zero before publishing synthetic output |
| Deadline reserve reached | Preserve one controlled result per remaining task |

## Delivery Proof

- Final image: `v3.3.0-full-hybrid`
- OCI manifest digest: `sha256:6bcff04a9b5929b3788345d41304e3d6b98a9901116546afb16ae1e9445139ed`
- Platform digest: `sha256:60677fbae98c2043f4c708de8cac00967cdcf5c41a0ef18f24cf0c116de9f2a0`
- Compressed size: 2,666,216,379 bytes
- Source revision: `cfeacd407ac7488883afdc6df580fb86b48a039e`
- Release run: `29158458646`
- Exact local-inference run: `29158947843`
- Compact rollback: `v2.1.0-proof-router`

## Evidence Boundaries

The 80-row balanced arena is a frozen holdout replay plus exact-image envelope projection, not a live 80-row container run. Historical rejected policies remain in the repository for reproducibility and are explicitly marked as historical. Current release truth is defined by this document, `README.md`, `SUBMISSION.md` and `submission/final/final-release-decision.json`.

## Non-Goals

- No LLM judge in the runtime answer path.
- No embeddings, RAG or multimodality.
- No hardcoded or cached answers.
- No API-dollar optimization in place of the official token objective.
