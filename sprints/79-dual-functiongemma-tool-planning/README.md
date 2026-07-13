# Sprint 79 - Dual FunctionGemma Tool Planning

## Status

**Planned.** This Sprint does not modify the stable public image until a dedicated FunctionGemma planner passes every promotion gate.

## Objective

Replace Gemma 4 E2B as the structured tool planner with a second, independently fine-tuned FunctionGemma 270M while preserving the existing assessment model and E2B answer model.

```text
raw prompt
  -> FunctionGemma Assessment 270M
  -> existing regression and route policy
  -> narrow deterministic tool prefilter
  -> FunctionGemma Tool Planner 270M
  -> tool-plan-v2 schema and semantic provenance
  -> deterministic tool execution and recomputable proof
  -> mechanical exact-answer rendering
  -> Answer Contract Engine
  -> local release or Fireworks fallback

Non-tool route:
  -> existing Gemma 4 E2B LiteRT or Fireworks
```

The two FunctionGemma models share an architecture but not trained weights. They are separate, hash-pinned `.litertlm` artifacts. Runtime parameters cannot substitute for the second fine-tune.

## Guiding Principles

- Accuracy gates precede token savings.
- Prove memory and latency before training.
- Keep the existing assessment checkpoint immutable.
- Train the planner as a separate artifact to avoid assessment regression.
- Never let planner confidence authorize execution or release.
- Prefer mechanical exact answers over a second LLM rendering call.
- Fail closed to the existing Fireworks route on every uncertainty.
- Preserve `v3.8.2-e2b-contract` as rollback until a new exact image passes.

## Phase 0 - Freeze Baselines

- [ ] Pin the current FunctionGemma assessment artifact, calibration and SHA-256.
- [ ] Pin the current Gemma 4 E2B LiteRT artifact and SHA-256.
- [ ] Pin `tool-plan-v2`, `tool-evidence-v1` and Answer Contract v2.
- [ ] Freeze Sprint 78's 500-lineage corpus and sealed split.
- [ ] Record the stable image digest and public-pull evidence.
- [ ] Record baseline memory, cold start, throughput, route coverage and accuracy.
- [ ] Prevent all training and threshold code from reading sealed labels.

**Gate 0:** Every baseline artifact and split is immutable and reproducible.

## Phase 1 - Dual-Model Capacity Gate

Before training, duplicate the current FunctionGemma artifact under a second model ID. This isolates the cost of two loaded 270M engines from model-quality questions.

- [ ] Build a parallel experimental Docker image with assessment FunctionGemma, duplicate planner FunctionGemma and current E2B.
- [ ] Run the assessment and planner as independent local model endpoints.
- [ ] Load both FunctionGemma engines simultaneously rather than swapping per task.
- [ ] Keep E2B available in the same container.
- [ ] Disable network and all startup downloads.
- [ ] Apply `linux/amd64`, 4 GB RAM, 2 vCPU and 256 PID limits.
- [ ] Measure cold start and peak memory before inference.
- [ ] Invoke assessment, planner and E2B sequentially and measure peak memory during inference.
- [ ] Run 25 mixed tasks to detect cache growth or memory leakage.
- [ ] Confirm no OOM, restart, deadlock or model-ID collision.
- [ ] Measure the overhead relative to the stable image.

**Gate 1:** Peak sampled memory at most 3.6 GiB, cold start at most 30 seconds, and no failure under the exact resource envelope. Stop the Sprint if this fails.

## Phase 2 - Planner Contract And Prefilter

- [ ] Retain the strict `tool-plan-v2` top-level schema and version field.
- [ ] Retain allowlisted tools only: inventory, recipe cost, bounded arithmetic and ordering logic.
- [ ] Keep Python, shell, filesystem, imports and network execution excluded.
- [ ] Freeze the narrow structural prefilter independently of planner training.
- [ ] Ensure the prefilter can reject unsupported prompts without an extra model call.
- [ ] Require high confidence and complete explicit arguments for executable plans.
- [ ] Verify numbers, semantic roles, operation order, AST structure and relation direction mechanically.
- [ ] Reject old schemas, unknown keys, code fences with surrounding text and malformed JSON.
- [ ] Assign stable reason codes to every rejection and fallback path.

**Gate 2:** The deterministic validator reproduces 500/500 expected corpus decisions and executes 0/100 unsupported controls.

## Phase 3 - Training Corpus V2

- [ ] Convert each accepted plan into FunctionGemma's native function-calling training format.
- [ ] Include `none` examples as explicit no-tool targets rather than empty responses.
- [ ] Expand each supported family to at least 500 independent lineages.
- [ ] Expand unsupported and adversarial controls to at least 500 lineages.
- [ ] Include easy, moderate, difficult, ambiguous and intentionally incomplete tasks.
- [ ] Add swapped roles, reordered operations, repeated numbers and distractor quantities.
- [ ] Add wrong-tool near neighbors such as recipe versus calculator and inventory versus arithmetic.
- [ ] Add prompt-injection, schema-smuggling and invented-argument attacks.
- [ ] Generate controlled paraphrases without reusing exact evaluation templates.
- [ ] Deduplicate normalized prompts and plans.
- [ ] Group all mutations by root lineage before splitting.
- [ ] Allocate train, validation, calibration and sealed holdout by lineage.
- [ ] Keep at least 20% of lineages outside training and prompt iteration.
- [ ] Audit a stratified sample manually and with deterministic validators.
- [ ] Record provider, generation prompt, seed, lineage and hash provenance.

**Gate 3:** At least 2,500 clean unique lineages, zero split leakage and zero schema-invalid targets.

## Phase 4 - RTX 4060 QLoRA Training

- [ ] Use the exact official FunctionGemma 270M base revision associated with the current LiteRT model.
- [ ] Train a new planner adapter; never continue from the assessment adapter.
- [ ] Use QLoRA, gradient checkpointing and batch accumulation sized for 8 GB VRAM.
- [ ] Begin with a short learning-rate range and overfit smoke on 50 examples.
- [ ] Require the overfit smoke to reach at least 98% exact-plan accuracy.
- [ ] Run one bounded baseline training job before tuning hyperparameters.
- [ ] Track train and validation loss, schema validity, tool accuracy and exact-plan accuracy.
- [ ] Stop on validation degradation or increasing unsafe false positives.
- [ ] Compare one, two and three epochs without selecting on sealed data.
- [ ] Save adapter, optimizer metadata, base revision, tokenizer and training manifest.
- [ ] Reproduce the chosen checkpoint from one command.

**Gate 4:** Validation schema validity at least 99%, supported-tool precision at least 97%, and unsupported false-positive rate at most 1%.

## Phase 5 - Merge, Quantize And LiteRT Export

- [ ] Merge the selected LoRA adapter into the exact FunctionGemma base.
- [ ] Compare merged BF16 output against adapter-on-base output.
- [ ] Quantize the merged planner using the same supported LiteRT quantization family as the existing FunctionGemma artifact.
- [ ] Export a standalone planner `.litertlm` with a distinct model ID.
- [ ] Pin converter, LiteRT-LM and tokenizer versions.
- [ ] Record pre-merge, merged and quantized hashes.
- [ ] Compare at least 200 prompts across adapter, merged and LiteRT artifacts.
- [ ] Treat output truncation, schema drift and tool-call drift as conversion failures.
- [ ] Reject conversion if the supported LiteRT toolchain cannot reproduce the fine-tuned model reliably.

**Gate 5:** At least 99% tool-choice agreement and 98% executable-plan agreement between merged and LiteRT planner outputs, with no increase in unsafe releases.

## Phase 6 - Planner Evaluation Ladder

Run increasingly expensive evaluations and stop immediately on a failed gate.

### Level A - 40 Tasks

- [ ] Ten tasks per supported tool family plus unsupported controls.
- [ ] Verify schema, semantic provenance, proof and final answer.
- [ ] Require zero unsafe false positives.

### Level B - 200 Tasks

- [ ] Balance families, difficulty and negative controls.
- [ ] Require at least 95% precision among locally released answers.
- [ ] Require at least 90% observed precision for every promoted family.

### Level C - 800 Tasks

- [ ] Use 100 tasks from each Track 1 category.
- [ ] Measure prefilter recall, planner precision, proof acceptance and Fireworks avoidance.
- [ ] Compare against the current assessment/E2B/Fireworks runtime.

### Level D - Full Available Corpus

- [ ] Run every independent tool-planner lineage only after Levels A-C pass.
- [ ] Do not rerun the old 4,000 E2B-answer corpus unless E2B weights or routing behavior changes.
- [ ] Revalidate only tasks whose route can change because of the new planner.
- [ ] Preserve untouched E2B evidence when the E2B artifact and prompt remain byte-identical.

**Gate 6:** Global released-answer precision at least 95%, 90% Wilson lower bound at least 85% per promoted family, and zero unsafe control execution on the sealed holdout.

## Phase 7 - Dual-FunctionGemma Orchestration

- [ ] Keep assessment and planner clients separate and explicitly named.
- [ ] Call assessment on the existing route exactly as today.
- [ ] Call the planner only after the deterministic prefilter accepts the prompt.
- [ ] Bound planner tokens and deadline independently from E2B and Fireworks.
- [ ] Skip E2B when a deterministic proof can render the exact final answer.
- [ ] Preserve E2B for existing validated local cohorts only.
- [ ] Preserve dynamic `FIREWORKS_BASE_URL` and `ALLOWED_MODELS` authorization.
- [ ] Fall back directly to Fireworks on planner timeout, invalid plan, invalid proof or contract failure.
- [ ] Emit route, model hash, planner decision, proof hash and fallback reason without logging sensitive prompt data.
- [ ] Ensure one task failure cannot corrupt or omit other results.

**Gate 7:** Every transition has success, timeout, malformed-output, OOM and fallback tests. Existing assessment and E2B route decisions remain byte-for-byte unchanged outside the tool cohort.

## Phase 8 - Ten-Minute Championship Arena

- [ ] Build an adversarial worst-case batch dominated by prefilter-positive prompts.
- [ ] Build uniform, math-heavy, logic-heavy and ordinary Track 1 distributions.
- [ ] Measure cold start, total runtime, peak memory, local calls, Fireworks calls and tokens.
- [ ] Count both FunctionGemma calls in local latency even though they cost zero Fireworks tokens.
- [ ] Require complete task coverage and valid official output.
- [ ] Compare accuracy and tokens against `v3.8.2-e2b-contract` on identical tasks.
- [ ] Test with 4 GB RAM, 2 vCPU, `linux/amd64`, no network and no startup downloads.
- [ ] Repeat the worst-case run at least three times.

**Gate 8:** Every run finishes within 540 seconds, leaving a 60-second safety margin; peak sampled memory remains at most 3.6 GiB; accuracy does not regress; Fireworks tokens decrease on at least one realistic distribution.

## Phase 9 - Release And Rollback

- [ ] Build one immutable challenger image without overwriting any existing tag.
- [ ] Confirm compressed image size below 10 GB.
- [ ] Pull from a clean machine and audit the public `linux/amd64` manifest.
- [ ] Run official input/output, missing-env, invalid-env and Fireworks-failure drills.
- [ ] Run secret and cached-answer scans.
- [ ] Publish policy, model, dataset and image hashes.
- [ ] Update README, architecture, public report and demo claims only after measurements exist.
- [ ] Preserve `v3.8.2-e2b-contract` as a one-field rollback.
- [ ] Record an explicit promote or retain decision.

## Required Artifacts

- [ ] `configs/functiongemma-tool-planner-v1.json`
- [ ] `configs/dual-functiongemma-policy-v1.json`
- [ ] Planner training and sealed dataset manifests.
- [ ] Hash-pinned planner LoRA adapter.
- [ ] Hash-pinned merged checkpoint.
- [ ] Hash-pinned quantized planner `.litertlm`.
- [ ] Dual-model resource-gate report.
- [ ] Quantization and LiteRT parity report.
- [ ] Planner accuracy and safety report.
- [ ] Ten-minute championship report.
- [ ] Public architecture and promotion report.

## Stop Conditions

Stop and retain the stable image immediately if any condition occurs:

- Dual FunctionGemma plus E2B exceeds 3.6 GiB sampled memory.
- The second local engine causes unstable startup or model swapping.
- FunctionGemma cannot learn `tool-plan-v2` above the precision floor.
- LiteRT conversion is unavailable or materially changes planner decisions.
- Any unsupported sealed control executes a tool.
- Released-answer precision falls below 95%.
- Worst-case runtime exceeds 540 seconds.
- The challenger saves no Fireworks tokens on realistic distributions.

## Estimated Execution Time

| Phase | Expected time |
|---|---:|
| Baseline and dual-model capacity gate | 1-2 hours |
| Corpus expansion and audit | 3-6 hours |
| QLoRA smoke and bounded training | 2-5 hours |
| Merge, quantization and LiteRT export | 1-4 hours |
| Evaluation ladder | 2-6 hours |
| Docker championship and release | 2-4 hours |

The estimates exclude unexpected LiteRT converter incompatibilities. Each gate is intentionally ordered so a cheap failure prevents later spending.

## Definition Of Done

- [ ] Two distinct FunctionGemma artifacts run under the exact evaluator envelope.
- [ ] The planner model is trained, converted and hash-pinned independently from assessment.
- [ ] Every released tool answer has a recomputable deterministic proof.
- [ ] Existing assessment, E2B and Fireworks behavior remains unchanged outside the tool cohort.
- [ ] The exact challenger image passes accuracy, memory, time, I/O, public-pull and size gates.
- [ ] The Sprint records an evidence-backed `promote` or `retain` decision.
