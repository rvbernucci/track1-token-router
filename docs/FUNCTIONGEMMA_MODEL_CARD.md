# FunctionGemma Track 1 Assessor Model Card

Status: **scale-789 Q8 runtime champion promoted; final container gate pending**
Base: `google/functiongemma-270m-it`
Base revision: `39eccb091651513a5dfb56892d3714c1b5b8276c`

## Intended Use

This model converts one unseen AMD Hackathon Track 1 text task into exactly one `assess_task` function call containing an eight-class intent and five ordinal scores. Sub-intent remains dataset metadata and is intentionally omitted from the 270M target. The model does not answer the task, select an execution engine, select a Fireworks model or emit chain-of-thought.

The assessment feeds a code-owned regression and minimax-regret decision engine. Invalid output fails closed to Fireworks.

## Contract

- Assessment schema: `task-assessment-v1`
- Taxonomy: `track1-sub-intents-v1`
- Rubric: `assessment-rubric-v2`
- Tool definition source: `router/functiongemma/tooling.py`
- Output: one native FunctionGemma call to `assess_task`
- Disallowed: natural-language answer, extra call, `engine`, `route`, `model_id`, confidence or additional fields

## Data

The first pilot contains 120 accepted teacher proposals. The scale run generated 1,000 proposals, validated all 1,000, removed 13 duplicates and adjudicated 789 as accepted with 198 retained for review. Its frozen split is 696 train and 93 validation; the original 24 teacher-blind cases remain separate. Template families and mutation lineages are assigned as connected components to prevent leakage.

The training prompt distribution, measured with the FunctionGemma tokenizer, is: minimum 574, p50 635, p90 755, p95 810, p99 906 and maximum 955 tokens. Training uses `max_length=1024`; no pilot row is truncated.

Raw examples, provider responses, rationales and hidden labels are private. Aggregate provenance and quality evidence is published in `reports/public/functiongemma-dataset-pilot.md`.

## Training Candidates

| Candidate | Method | Rank | Status |
|---|---|---:|---|
| Untuned base | No training | - | 0% valid under the task-specific tool contract |
| Full SFT pilot | All parameters | - | 100% schema, 75.0% intent on pilot validation |
| LoRA R8 pilot | LoRA, merged before evaluation | 8 | Rejected: 87.5% schema, 56.25% intent |
| LoRA R16 pilot | LoRA, merged before evaluation | 16 | Pilot champion: 100% schema, 81.25% intent |
| LoRA R16 scale-789 | LoRA, merged before evaluation | 16 | Provisional champion: 100% schema, 95.70% intent |
| LoRA R16 combined-1621 | LoRA, merged before evaluation | 16 | Rejected: 99.00% schema on combined validation despite 95.52% intent |

All candidates use the same immutable base revision, data splits, seed and evaluation code. A candidate cannot be promoted unless exact schema validity is at least 99.9%, intent accuracy does not regress and every promoted score dimension beats the untuned validation baseline.

## Evaluation

Scale-789 validation (`n=93`) reports:

- schema validity: `100%`;
- intent accuracy: `95.70%`;
- p50/p95: `1025/1084 ms` on the AMD pod;
- score MAE: deterministic `3.16`, reasoning `1.45`, knowledge `1.69`, generation `1.71`, format `1.60`.

The frozen 24-case diagnostic hidden set reports `100%` schema and `75%` intent. It is no longer used for tuning; a fresh final holdout is required before submission.

The combined challenger used 1,420 training and 201 lineage-disjoint development-validation examples. On the same 201-case validation set, it improved intent accuracy from `92.04%` to `95.52%` relative to scale-789, but produced two invalid calls (`199/201`, `99.00%`). It also regressed knowledge-uncertainty MAE from `1.85` to `4.60` and reasoning-demand MAE from `1.46` to `1.64`. The scale-789 model therefore remains champion under the schema-first promotion policy. The combined run is useful evidence that the new data improves intent generalization, not a deployable artifact.

The promoted deployment artifact is the merged scale-789 model converted to GGUF `Q8_0` with official `llama.cpp` release `b9948`. It is `291,557,568` bytes with SHA-256 `74625dd27cf25d54018fa17328a1b1b43f1f09c179e1e4edfaeeffc0c05d9b77`. Under the final two-thread OpenAI-compatible protocol, Q8 and BF16 produced identical raw calls and parsed assessments on all 93 validation tasks. At the promoted 64-token cap, Q8 achieved `100%` schema validity, `96.77%` intent accuracy, p50 `990 ms` and p95 `1,201 ms`.

The final card will additionally report:

- exact native-call/schema validity;
- intent accuracy;
- MAE and weighted quadratic kappa for every score;
- boundary-pair ordering;
- promoted ordinal calibration mappings;
- p50/p95 assessment latency and peak RSS;
- end-to-end answer accuracy and Fireworks token impact.

Ordinal calibration promotes only deterministic fit, format complexity and generation demand because the other two dimensions do not improve. Boundary ordering over 41 lineage-matched comparisons is `43.90%` strict and `67.07%` tie-adjusted, with four inversions. Downstream selection must therefore propagate score residuals and avoid brittle thresholds. Remaining championship blockers are a fresh final holdout and the combined 4 GB / 2 vCPU container test.

## Runtime And Safety

- deterministic decoding;
- strict parser with exact enum and field validation;
- one call only, no surrounding text;
- no evaluator-time model downloads;
- invalid, timed-out or unavailable local assessment routes to Fireworks-safe mode;
- final artifact is GGUF Q8 and must pass a 4 GB RAM / 2 vCPU combined-container test.

## Known Limitations

FunctionGemma has only 270M parameters and is specialized for function calling. Fine-tuning can improve task assessment but does not make it a general verifier or solver. It may misread indirect intent, adversarial instructions, new domains or tasks outside the eight official categories. The mathematical selector must account for calibrated residual uncertainty rather than treating scores as ground truth.

## Reproducibility

The checked-in experiment pins Python, ROCm Torch, Transformers, Datasets, Accelerate, PEFT and TRL versions measured on the AMD pod. Training refuses to start if those versions diverge. The checked-in artifact manifest records model, dataset, tool schema, calibration, runtime, environment and Git state hashes.

## Primary References

- [FunctionGemma overview](https://ai.google.dev/gemma/docs/functiongemma)
- [FunctionGemma fine-tuning](https://ai.google.dev/gemma/docs/functiongemma/finetuning-with-functiongemma)
- [FunctionGemma formatting](https://ai.google.dev/gemma/docs/functiongemma/formatting-and-best-practices)
- [FunctionGemma model card](https://ai.google.dev/gemma/docs/functiongemma/model_card)
