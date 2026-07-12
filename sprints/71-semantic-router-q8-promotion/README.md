# Sprint 71 - Semantic Router Q8 Promotion

## Timebox

`45 minutes`, with AMD GPU work running in parallel with local evidence preparation. Stop at the timebox and retain the current Q8 artifact unless the challenger has complete parity evidence.

## Objective

Promote the semantic-v3 FunctionGemma 270M full-SFT challenger only if its Q8 artifact preserves structured-output reliability, intent accuracy, score behavior and the official two-thread runtime envelope.

## Completed Evidence

- [x] Label all `6,845` ledger prompts with two semantic teachers and retain disagreements explicitly.
- [x] Build lineage-safe `fit` and `calibration` splits while excluding protected rows from training.
- [x] Train full SFT and LoRA R16 from the pinned FunctionGemma revision.
- [x] Select full SFT over LoRA using the `1,124`-row calibration holdout.
- [x] Achieve `100%` BF16 schema validity and `97.51%` intent accuracy on calibration.
- [x] Score all `6,845` prompts with production-available outputs only.
- [x] Convert the winner with pinned `llama.cpp b9948` and produce a `Q8_0` GGUF of approximately `279 MB`.

## Completed Decision Work

- [x] Complete Q8 inference on all `1,124` calibration prompts through `llama-server` with two CPU threads.
- [x] Compare BF16 and Q8 parsed assessments by immutable task ID.
- [x] Report schema validity, intent accuracy, five score MAEs, p50/p95 latency and parsed-call parity.
- [x] Re-run the `201`-row historical holdout through Q8.
- [x] Reject Q8: calibration intent regressed by `0.534 pp` and historical schema validity was `99.50%`.
- [x] Generate an artifact manifest with base revision, training data hashes, tool hash, converter commit, bytes and SHA-256.
- [x] Keep the rejected F16 intermediate outside Docker; no rejected artifact enters the release image.

## Gate Results

- [x] Calibration schema validity passed at `100%`; historical validity failed at `99.50%`.
- [x] Intent non-inferiority failed narrowly: `0.534 pp` regression versus the frozen `0.5 pp` margin.
- [x] No invalid Q8 assessment is eligible for E2B; invalid output routes directly to Fireworks.
- [x] The artifact loaded with two threads and no network access.
- [x] The rejected artifact is not a replacement and cannot increase the release image.

## Rollback

Retain the scale-789 Q8 artifact and `v3.6.0-category-calibrated` image until every Sprint 75 release gate passes.

## Definition of Done

- [x] The scale-789 Q8 champion remains frozen; the semantic-v3 challenger decision and hash are immutable.
- [x] No downstream regression may use semantic-v3 BF16 behavior; Sprint 72 must use production runtime outputs.
