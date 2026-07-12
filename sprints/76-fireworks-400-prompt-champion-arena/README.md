# Sprint 76 - Fireworks 800-Prompt Champion Arena

## Final Status

**Closed as `retain`; no Sprint 76 policy was promoted.** The complete paired arena is reproducible, but it failed the absolute accuracy gates and the initial analysis included final-holdout rows before policy freeze. See `reports/public/fireworks-champion-v3.md` for the evidence and limitations. The absent `configs/fireworks-intent-policy-v3.json` is an intentional fail-closed outcome.

## Parallel Contract

This sprint runs concurrently with Sprint 77. It owns remote-model inference, blind judging and the Fireworks intent policy. Sprint 77 may consume the frozen judgments only after this sprint writes its immutable ledger; it must not modify arena prompts, candidates or labels.

## Objective

Determine where Kimi K2.7 Code and MiniMax M3 are accurate, contract-compliant and token-efficient on a frozen, balanced 800-prompt sample from the 4,400-prompt E2B corpora. Promote the smallest per-intent policy that maximizes accuracy before token savings.

## Scope And Budget

- [ ] Freeze exactly 800 prompts: 100 from each of the eight official categories.
- [ ] Run both models on every prompt for exactly 1,600 paired Fireworks calls.
- [ ] Sample from both E2B expansion and regression corpora; do not generate synthetic arena replacements.
- [ ] Stratify every category across source, lineage, easy, medium and hard metadata when available.
- [ ] Preserve mutation lineage so near-duplicates cannot cross selection and audit splits.
- [ ] Preserve the original train, calibration, validation and final-holdout boundaries instead of resampling rows freely.
- [ ] Estimate worst-case spend before the first call and refuse to start above `$5` projected spend.
- [ ] Enforce an absolute `$7` hard stop and retain the remaining Fireworks credit as paid-account protection.
- [ ] Stop automatically if projected spend, failure rate or remaining time violates the release reserve.

## Frozen Dataset

- [ ] Build `evals/fireworks-champion-v3/tasks.jsonl` with 800 task IDs, prompts, categories, difficulties, sources and lineages.
- [ ] Join metadata to `inputs`, `splits` and `sealed/tasks` by immutable task ID; metadata files do not contain prompt text.
- [ ] Fail the build on missing joins, divergent prompts, duplicate task IDs or duplicate prompt hashes.
- [ ] Exclude prompts known to be malformed, duplicate or dependent on current facts without a frozen reference.
- [ ] Hash the task file and record source-file hashes in `manifest.json`.
- [ ] Keep answer references and E2B correctness labels out of model requests.
- [ ] Preserve every source's existing protected audit split before making the first Fireworks call.
- [ ] Add tests for category counts, lineage isolation, deterministic sampling and prompt uniqueness.

## Runtime-Parity Paired Inference

- [ ] Send one raw user message with no task ID, JSON envelope, routing metadata or answer reference.
- [ ] Use temperature zero, `reasoning_effort=none` and the production dynamic completion-token policy.
- [ ] Execute bounded concurrent workers independently for Kimi and MiniMax.
- [ ] Cap concurrency per model and retry only transport or provider failures, never invalid answers.
- [ ] Persist each response atomically with model, request parameters, latency and token usage.
- [ ] Resume safely from completed `(task_id, model)` pairs without duplicate calls.
- [ ] Treat missing content, truncation and malformed responses as observed failures.
- [ ] Route every call through the configured Fireworks base URL and permitted model IDs.

## Accuracy Adjudication

- [ ] Apply deterministic validators first for arithmetic, logic, executable code, JSON, NER and explicit format constraints.
- [ ] Present semantically judged candidates to Codex 5.5 high-reasoning as randomized `candidate_a` and `candidate_b`.
- [ ] Require the judge to mark each candidate independently valid or invalid before choosing a winner.
- [ ] Blind the judge to model identity, tokens, latency, routing features and previous policy.
- [ ] Avoid Codex calls where deterministic execution, exact references or contract checks already prove the outcome.
- [ ] Rejudge model disagreements, ambiguous sentiment and reference-free factual answers with a second independent pass.
- [ ] Count a model correct only when the mechanical validator passes or the frozen judge policy accepts it.
- [ ] Report accuracy, truncation, contract failure, tokens and latency per category and difficulty.

## Policy Estimation

- [ ] Compare always-Kimi, always-MiniMax and per-intent selection on identical rows.
- [ ] Optimize lexicographically: validity, worst-category validity, total tokens, then latency.
- [ ] Calculate paired accuracy deltas and bootstrap confidence intervals grouped by lineage.
- [ ] Calculate Wilson lower bounds for every promoted category/model combination.
- [ ] Do not use Nash mixing when one model strictly dominates on accuracy and tokens.
- [ ] Use minimax regret only for unsupported or statistically tied strata.
- [ ] Preserve `ALLOWED_MODELS` as the runtime authorization boundary.

## Promotion Gates

- [ ] Development accuracy is at least `95%` globally and no category is below `90%`.
- [ ] Sealed audit accuracy does not regress against always-Kimi.
- [ ] A category override requires at least 80 development rows and no statistically significant accuracy loss versus the category champion.
- [ ] Any token-saving override must preserve the accuracy winner within the paired confidence interval.
- [ ] Missing preferred models degrade to an authorized available model.
- [ ] The selected policy passes the official public retired sample and Answer Contract Engine tests.

## Deliverables

- [ ] `scripts/build_fireworks_champion_v3.py` freezes the 800-prompt arena.
- [ ] `scripts/run_fireworks_champion_v3.py` performs resumable concurrent paired calls.
- [ ] `scripts/judge_fireworks_champion_v3.py` merges mechanical and blind judgments.
- [ ] `reports/public/fireworks-champion-v3.md` records results and limitations.
- [ ] `configs/fireworks-intent-policy-v3.json` is written only if all promotion gates pass.
- [ ] The exact candidate image is rebuilt and independently gated before submission.

## Definition Of Done

- [ ] All 1,600 paired calls are accounted for; every semantic-judge queue row has a completed blind decision.
- [ ] The sealed split is opened once, after policy freeze.
- [ ] One explicit `promote` or `retain` decision is committed with reproducible hashes.
- [ ] No unverified policy change reaches the submitted image.
