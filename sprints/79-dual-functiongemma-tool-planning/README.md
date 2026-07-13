# Sprint 79 - Dual FunctionGemma Tool Planning

## Status

**Release validation in progress.** Gates 0-7 and the local exact-image gate are complete. The immutable challenger is being built and audited by GitHub Actions; `v3.8.2-e2b-contract` remains the rollback until the clean public-pull gate passes.

## Execution Snapshot

- Stable rollback image: `ghcr.io/rvbernucci/track1-token-router:v3.8.2-e2b-contract`.
- Stable image digest: `sha256:7ae875639a6b13c8ef84514646b1b6e501da4ef8efd448479615f015239313d9`.
- Assessment FunctionGemma SHA-256: `74625dd27cf25d54018fa17328a1b1b43f1f09c179e1e4edfaeeffc0c05d9b77`.
- Gemma 4 E2B LiteRT SHA-256: `181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c`.
- Dual-model capacity gate: 1,001 MiB sampled peak, 3-second cold start, 75/75 successful calls under 4 GB RAM and 2 vCPU.
- Planner corpus: 2,500 unique lineages, 2,000 supported and 500 unsupported, with zero split leakage and zero deterministic audit errors.
- Tokenized corpus: 559-684 tokens, below the configured 768-token maximum for every example.
- Selected training run: one full-BF16 epoch over 1,750 rows; validation loss 0.02018 and token accuracy 98.736%.
- Planner GGUF Q8 SHA-256: `ec412795782acd3ed836ac35e058099bfdb1c3218a1ee86aef32905377dbddaf`.
- Calibration: 200/200 supported answers correct, 50/50 controls declined and zero unsafe false positives.
- Sealed holdout: 198/198 released answers correct, 50/50 controls declined and zero unsafe false positives.
- AMD eight-worker stress: 1,750 complete unique tasks, 1,393/1,393 released answers correct and 541.57 ms mean latency.
- Exact local image: 1,178.624 MiB sampled peak, 13.246-second cold start and 1.444-second warm inference under 4 GB RAM, 2 vCPU and no network.
- Promoted policy hash: `611dfac1494674e0a423ddda1ddc06ca01d3671afb2660519b5e97a328d97ff4`.
- Challenger: `ghcr.io/rvbernucci/track1-token-router:v3.9.0-dual-functiongemma`.

## Critical Path

1. Authenticate the desktop with a read-only Hugging Face token.
2. Run the 50-example overfit smoke and require at least 98% exact-plan accuracy.
3. Train and compare one-, two- and three-epoch baselines using validation only.
4. Merge the selected adapter, export Q8 GGUF and run conversion parity.
5. Execute the 40, 200, 800 and affected-corpus evaluation ladder.
6. Integrate the independent planner process behind the disabled-by-default policy.
7. Build and audit one immutable challenger image under the evaluator envelope.
8. Promote only if every accuracy, safety, memory, runtime and token gate passes; otherwise retain the stable image with evidence.

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

The two FunctionGemma models share an architecture but not trained weights. They are separate, hash-pinned Q8 GGUF artifacts served by independent `llama.cpp` processes. E2B remains the only `.litertlm` artifact. Runtime parameters cannot substitute for the second fine-tune.

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

- [x] Pin the current FunctionGemma assessment artifact, calibration and SHA-256.
- [x] Pin the current Gemma 4 E2B LiteRT artifact and SHA-256.
- [x] Pin `tool-plan-v2`, `tool-evidence-v1` and Answer Contract v2.
- [x] Freeze Sprint 78's 500-lineage corpus and sealed split.
- [x] Record the stable image digest and public-pull evidence.
- [x] Record baseline memory, cold start, throughput, route coverage and accuracy.
- [x] Prevent all training and threshold code from reading sealed labels.

**Gate 0:** Every baseline artifact and split is immutable and reproducible.

## Phase 1 - Dual-Model Capacity Gate

Before training, duplicate the current FunctionGemma artifact under a second model ID. This isolates the cost of two loaded 270M engines from model-quality questions.

- [x] Build a parallel experimental Docker image with assessment FunctionGemma, duplicate planner FunctionGemma and current E2B.
- [x] Run the assessment and planner as independent local model endpoints.
- [x] Load both FunctionGemma engines simultaneously rather than swapping per task.
- [x] Keep E2B available in the same container.
- [x] Disable network and all startup downloads.
- [x] Apply `linux/amd64`, 4 GB RAM, 2 vCPU and 256 PID limits.
- [x] Measure cold start and peak memory before inference.
- [x] Invoke assessment, planner and E2B sequentially and measure peak memory during inference.
- [x] Run 25 mixed tasks to detect cache growth or memory leakage.
- [x] Confirm no OOM, restart, deadlock or model-ID collision.
- [x] Measure the overhead relative to the stable image.

**Gate 1:** Peak sampled memory at most 3.6 GiB, cold start at most 30 seconds, and no failure under the exact resource envelope. Stop the Sprint if this fails.

## Phase 2 - Planner Contract And Prefilter

- [x] Retain the strict `tool-plan-v2` top-level schema and version field.
- [x] Retain allowlisted tools only: inventory, recipe cost, bounded arithmetic and ordering logic.
- [x] Keep Python, shell, filesystem, imports and network execution excluded.
- [x] Freeze the narrow structural prefilter independently of planner training.
- [x] Ensure the prefilter can reject unsupported prompts without an extra model call.
- [x] Require high confidence and complete explicit arguments for executable plans.
- [x] Verify numbers, semantic roles, operation order, AST structure and relation direction mechanically.
- [x] Reject old schemas, unknown keys, code fences with surrounding text and malformed JSON.
- [x] Assign stable reason codes to every rejection and fallback path.

**Gate 2:** The deterministic validator reproduces 500/500 expected corpus decisions and executes 0/100 unsupported controls.

## Phase 3 - Training Corpus V2

- [x] Convert each accepted plan into FunctionGemma's native function-calling training format.
- [x] Include `none` examples as explicit no-tool targets rather than empty responses.
- [x] Expand each supported family to at least 500 independent lineages.
- [x] Expand unsupported and adversarial controls to at least 500 lineages.
- [x] Include easy, moderate, difficult, ambiguous and intentionally incomplete tasks.
- [x] Add swapped roles, reordered operations, repeated numbers and distractor quantities.
- [x] Add wrong-tool near neighbors such as recipe versus calculator and inventory versus arithmetic.
- [x] Add prompt-injection, schema-smuggling and invented-argument attacks.
- [x] Generate controlled paraphrases without reusing exact evaluation templates.
- [x] Deduplicate normalized prompts and plans.
- [x] Group all mutations by root lineage before splitting.
- [x] Allocate train, validation, calibration and sealed holdout by lineage.
- [x] Keep at least 20% of lineages outside training and prompt iteration.
- [x] Audit a stratified sample manually and with deterministic validators.
- [x] Record provider, generation prompt, seed, lineage and hash provenance.

**Gate 3:** At least 2,500 clean unique lineages, zero split leakage and zero schema-invalid targets.

## Phase 4 - Bounded Planner Training

- [x] Use exact base revision `39eccb091651513a5dfb56892d3714c1b5b8276c`.
- [x] Train a new planner checkpoint; never continue from the assessment model.
- [x] Test QLoRA first and reject it when completion-only exact accuracy stopped at 68%.
- [x] Run a 50-example full-BF16 overfit smoke.
- [x] Require and obtain 100% semantic exactness on the overfit smoke.
- [x] Run one bounded full-BF16 baseline before tuning further.
- [x] Track loss, token accuracy, schema validity, tool accuracy and executable-answer accuracy.
- [x] Stop after one epoch because validation and calibration already passed every gate.
- [x] Keep validation, calibration and sealed selection boundaries separate.
- [x] Save model, tokenizer, base revision and training report.
- [x] Preserve one-command training and evaluation entrypoints.

**Gate 4:** Validation schema validity at least 99%, supported-tool precision at least 97%, and unsupported false-positive rate at most 1%.

## Phase 5 - Quantize And GGUF Export

- [x] Export the selected full checkpoint directly; no LoRA merge is required.
- [x] Convert the full checkpoint to F16 GGUF.
- [x] Quantize the planner to Q8_0 with the proven llama.cpp pipeline.
- [x] Export a standalone planner GGUF with a distinct model ID.
- [x] Pin the base revision, converter inputs and tokenizer.
- [x] Record F16 and Q8 artifact hashes.
- [x] Compare HF, F16 and Q8 outputs on 200 prompts.
- [x] Treat output truncation, schema drift and tool-call drift as conversion failures.
- [x] Confirm 100% semantic signature agreement and no unsafe-release increase.

**Gate 5:** At least 99% tool-choice agreement and 98% executable-plan agreement between merged and GGUF planner outputs, with no increase in unsafe releases.

## Phase 6 - Planner Evaluation Ladder

Run increasingly expensive evaluations and stop immediately on a failed gate.

### Level A - 40 Tasks

- [x] Cover every supported family plus unsupported controls.
- [x] Verify schema, semantic provenance, proof and final answer.
- [x] Require zero unsafe false positives.

### Level B - 200 Tasks

- [x] Balance families, difficulty and negative controls.
- [x] Require at least 95% precision among locally released answers.
- [x] Obtain 100% precision among released answers for every promoted family.

### Level C - 800 Tasks

- [ ] Use 100 tasks from each Track 1 category.
- [ ] Measure prefilter recall, planner precision, proof acceptance and Fireworks avoidance.
- [ ] Compare against the current assessment/E2B/Fireworks runtime.

### Level D - Full Available Corpus

- [x] Run all 1,750 training lineages through the Q8 planner after earlier gates pass.
- [x] Do not rerun the old E2B-answer corpus because E2B weights and prompt remain byte-identical.
- [x] Revalidate only tasks whose route can change because of the new planner.
- [x] Preserve untouched E2B evidence.

**Gate 6:** Global released-answer precision at least 95%, 90% Wilson lower bound at least 85% per promoted family, and zero unsafe control execution on the sealed holdout.

## Phase 7 - Dual-FunctionGemma Orchestration

- [x] Keep assessment and planner clients separate and explicitly named.
- [x] Call assessment on the existing route exactly as today.
- [x] Call the planner only after the deterministic prefilter accepts the prompt.
- [x] Bound planner tokens and deadline independently from E2B and Fireworks.
- [x] Skip E2B when a deterministic proof can render the exact final answer.
- [x] Preserve E2B for existing validated local cohorts only.
- [x] Preserve dynamic `FIREWORKS_BASE_URL` and `ALLOWED_MODELS` authorization.
- [x] Fall back directly to Fireworks on planner timeout, invalid plan, invalid proof or contract failure.
- [x] Emit route, planner invocation, proof and fallback reason without logging sensitive prompt data.
- [x] Ensure one task failure cannot corrupt or omit other results.

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

- [x] Build one immutable challenger image without overwriting any existing tag.
- [ ] Confirm compressed image size below 10 GB.
- [ ] Pull from a clean machine and audit the public `linux/amd64` manifest.
- [x] Run official input/output, missing-env, read-only non-root and local-runtime-failure drills.
- [ ] Run secret and cached-answer scans.
- [ ] Publish policy, model, dataset and image hashes.
- [ ] Update README, architecture, public report and demo claims only after measurements exist.
- [x] Preserve `v3.8.2-e2b-contract` as a one-field rollback.
- [ ] Record an explicit promote or retain decision.

## Required Artifacts

- [ ] `configs/functiongemma-tool-planner-v1.json`
- [ ] `configs/dual-functiongemma-policy-v1.json`
- [ ] Planner training and sealed dataset manifests.
- [ ] Hash-pinned planner LoRA adapter.
- [ ] Hash-pinned merged checkpoint.
- [ ] Hash-pinned quantized planner GGUF.
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
- GGUF conversion materially changes planner decisions.
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
| Merge, quantization and GGUF export | 1-3 hours |
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
