# Sprint 46 - FunctionGemma Assessment Training

Status: **Completed and promoted on 2026-07-10**

## Objective

Train FunctionGemma 270M to infer one of eight `intent` values and five anchored scores without answering the task or selecting an engine.

## Dataset Design

- one original task per row;
- gold `intent` and dataset-only `sub_intent` for balanced coverage; the model target omits `sub_intent`;
- five integer labels with written justification stored outside model-visible content;
- boundary pairs that differ by one difficulty, freshness, length or format property;
- paraphrases, typos, multilingual prompts and prompt injection;
- split by source, template family and mutation lineage;
- hidden test labels unavailable to teacher models.

## Dataset Forge

The training dataset is produced by a resumable CLI pipeline, not by manual chat copy/paste:

```text
rubric + seed tasks
-> Claude Sonnet 5 primary generation/review
-> Antigravity fast parallel generation/rating
-> Fireworks bulk generation or quota fallback
-> schema and range validation
-> semantic deduplication
-> independent assessment and adjudication
-> lineage-safe train/validation/hidden-test manifests
```

Codex owns schemas, rubrics, deterministic boundary cases, orchestration, validators and reports. Claude Code with the exact model ID `claude-sonnet-5` is the preferred teacher for high-quality generation, review and independent adjudication. Antigravity CLI with `Gemini 3.5 Flash (Medium)` supplies fast parallel generation and an independent rating family. Fireworks supplies bulk generation, additional model diversity and continuity when account usage windows are exhausted. NativelyAI is optional for small seed experiments or a future review UI, but it is not a production dataset dependency because the current plan has no API, webhook or batch execution.

The forge must be dry-run by default. Claude Code runs against the authenticated Pro subscription and treats `total_cost_usd` only as equivalent usage telemetry, not as proof of an API charge. It must never switch silently to Anthropic Console/API pay-as-you-go. Fireworks generation requires an explicit USD budget. Every provider writes one append-only JSONL row at a time and persists a checkpoint after every completed batch. A first pilot of 100-200 examples must pass quality, quota and cost gates before scaling toward 10,000 examples.

### Provider Policy

- Pin Claude calls to `claude-sonnet-5`; never use the moving `sonnet` alias.
- Invoke Claude non-interactively with structured output and the minimum required tools/context.
- Invoke Antigravity non-interactively in `plan` mode and sandbox, with no repository or external API credentials.
- Pin Antigravity to the expected Google account through `DATASET_AGY_EXPECTED_EMAIL`; fail closed if the active account differs and never persist the address in dataset rows.
- Let the current Codex process orchestrate and validate concurrent Claude/Antigravity workers instead of recursively spawning an unrestricted Codex agent.
- Treat Claude Pro exhaustion as a resumable provider state, not a failed dataset run.
- On Claude quota exhaustion, either pause until the usage window resets or continue with Fireworks when the run policy explicitly allows it.
- Never enable Anthropic API pay-as-you-go as an automatic fallback.
- Keep provider roles configurable so generation, assessment and adjudication can use different models.
- Require independent adjudication: a model must not be the sole final judge of its own proposal.

### Dataset Row Lineage

Every row records:

- stable example and parent identifiers;
- source, template family and mutation lineage;
- teacher model and generation configuration;
- provider role, authentication mode and usage-window identifier;
- rubric and schema versions;
- raw proposal, validated labels and adjudication status;
- content hash, creation timestamp, token telemetry and billable Fireworks cost;
- split assignment made only after deduplication and lineage grouping.

## Checklist

- [x] Write a labeling handbook for all score anchors.
- [x] Label an adjudication seed with at least two independent raters.
- [x] Measure inter-rater agreement and resolve ambiguous dimensions.
- [x] Use mechanical evidence where possible instead of subjective labels.
- [x] Implement `dataset-forge` CLI commands for plan, generate, validate, deduplicate, adjudicate, split and report.
- [x] Make generation resumable with append-only JSONL, atomic checkpoints and idempotent example IDs.
- [x] Add a Claude Code provider pinned to `claude-sonnet-5` with JSON Schema output and restricted tools.
- [x] Add an Antigravity provider pinned to `Gemini 3.5 Flash (Medium)` with plan mode, sandbox and strict JSON parsing.
- [x] Support bounded concurrent provider workers without nondeterministic writes.
- [x] Detect Claude Pro quota exhaustion and checkpoint before pausing or applying an explicit Fireworks fallback policy.
- [x] Prohibit automatic Anthropic Console/API pay-as-you-go fallback.
- [x] Enforce per-run and cumulative USD budgets before every Fireworks request.
- [x] Store provider token telemetry, billable Fireworks cost and teacher provenance without storing credentials.
- [x] Add retry/backoff, partial-batch recovery and explicit terminal failure records.
- [x] Run a 100-200 example pilot and measure validity, duplication, disagreement and cost per accepted row.
- [x] Generate teacher proposals, independently assess them, then adjudicate and freeze gold labels.
- [x] Reject near-duplicate or same-lineage examples that would cross dataset splits.
- [x] Scale only after the pilot gates pass; 1,000 generated, 987 deduplicated and 789 accepted.
- [x] Measure the untuned FunctionGemma baseline.
- [x] Run full SFT on the AMD ROCm pod.
- [x] Compare LoRA rank 8 and 16 under identical splits.
- [x] Calibrate each score with held-out isotonic or ordinal calibration when beneficial.
- [x] Export the best 8-bit artifact first.
- [x] Record model, dataset, schema, rubric and environment hashes.

## Metrics

- generated, accepted, rejected and adjudicated rows;
- schema validity and semantic duplication rate;
- teacher/rater disagreement by score and intent;
- accepted rows per Claude Pro usage window;
- Sonnet-to-Fireworks provider handoff count and recovery rate;
- Fireworks tokens and USD per accepted gold row;
- recovery success after interrupted generation;
- exact assessment-schema validity;
- intent and sub-intent accuracy;
- mean absolute error per score;
- weighted quadratic kappa per score;
- calibration error and monotonicity;
- boundary-pair ordering accuracy;
- p50/p95 latency and peak RSS.

## Internal Gates

- dry-run performs zero network calls and zero spend;
- Claude generation uses the exact `claude-sonnet-5` model and the authenticated Pro plan;
- Claude quota exhaustion never loses rows and never triggers paid Anthropic API usage;
- paid runs cannot exceed their configured USD budget;
- interrupted runs resume without duplicate accepted rows;
- every accepted row has complete reproducible lineage;
- no template, source or mutation lineage crosses train, validation and hidden-test splits;
- the pilot demonstrates acceptable label agreement and cost before scale-up;
- assessment-schema validity at least 99.9%;
- no prompt can force an engine/model identifier into the output;
- score error and calibration beat the untuned baseline on every promoted dimension;
- boundary ordering is stable enough for the downstream regression;
- artifact is reproducible from pinned data and configuration.

## Deliverables

- tested Dataset Forge CLI and configuration schema;
- tested Claude Sonnet 5 provider and quota-safe Fireworks handoff;
- append-only raw, validated and adjudicated JSONL manifests;
- pilot quality/cost report and scale promotion decision;
- trained FunctionGemma assessment model;
- private train/validation/test manifests;
- public aggregate evaluation report;
- calibration transforms and model card.

## Current Evidence - 2026-07-10

- pilot: 120 generated, 120 schema-valid, zero duplicates, 120 accepted and zero unresolved;
- raters: Claude Sonnet 5, Gemini 3.5 Flash Medium and Fireworks Minimax M3;
- cost: `$0.0192993` billable Fireworks total;
- splits: 104 train, 16 validation and 24 private teacher-blind hidden cases;
- checked-in experiment: immutable FunctionGemma revision, full SFT, LoRA rank 8/16, strict native-call parser, ordinal calibration, champion selection and artifact manifest;
- AMD pod: ROCm/HIP and BF16 active; pinned `trl==0.26.2` verified against the AMD-provided stack without replacing Torch;
- tests: `366/366` repository tests passed after adding the capped E2B outcome runner, CPU-fixed LiteRT server, token ladder and independent teacher judge;
- authenticated base revision: `39eccb091651513a5dfb56892d3714c1b5b8276c`;
- contract v2 removed runtime `sub_intent`, reducing supervised tokens by about 35% and raising pilot schema validity to 100%;
- scale run: 1,000 generated, 987 deduplicated, 789 accepted, 696 train and 93 validation at `$0.94045175` total Fireworks spend;
- provisional champion: LoRA R16 scale-789, 100% schema and 95.70% validation intent accuracy;
- diagnostic hidden: 100% schema and 75% intent on 24 frozen cases; no further tuning against this set;
- the fresh final holdout and combined-container verification remain Sprint 49 championship gates.
- second teacher batch: 1,132 raw proposals from overlapping resumable runs, canonically reduced to 999 unique targets with 96 Sonnet and 903 Antigravity rows;
- second batch adjudication: 832 accepted, 167 retained for review, 724 train and 108 validation; combined development data is 1,420 train and 201 validation with zero lineage overlap;
- combined LoRA R16 training completed on the AMD pod in `785.99 s` with `2,567 MB` peak training RSS;
- same-set comparison on 201 development-validation cases: combined challenger `95.52%` intent and `99.00%` schema versus scale-789 `92.04%` intent and `100%` schema;
- combined challenger rejected by the schema-first gate after two malformed calls and severe knowledge-uncertainty MAE regression (`4.60` versus `1.85`); scale-789 remains champion;
- next repair experiment must preserve the combined model's new-batch intent gain while adding schema-hard negatives, score-distribution calibration and a fresh untouched holdout;
- promoted runtime artifact: merged scale-789 GGUF `Q8_0`, `291,557,568` bytes, SHA-256 `74625dd27cf25d54018fa17328a1b1b43f1f09c179e1e4edfaeeffc0c05d9b77`;
- pinned runtime: official `llama.cpp` release `b9948`, commit `074944998d3f25e7001ede30d152b59dff741c8c`, Linux `x64`, two CPU threads;
- final protocol: one required tool, deterministic decode and exact `<end_function_call>` stop framing;
- Q8 validation at a 64-token cap: `93/93` schema-valid, `90/93` intent-correct, p50 `990 ms`, p95 `1,201 ms` on the AMD pod;
- Q8 and BF16 produced identical raw calls and parsed assessments on `93/93` tasks under the final protocol;
- boundary evidence: 41 lineage-matched comparisons, 18 concordant, 19 ties and 4 inversions before calibration; tie-adjusted accuracy `67.07%`;
- calibration promotes deterministic fit, format complexity and generation demand; knowledge uncertainty and reasoning demand remain raw because calibration did not improve MAE;
- artifact and runtime manifests: `configs/functiongemma-scale789-q8-manifest.json` and `configs/functiongemma-scale789-q8-runtime.json`.

## Promotion Decision

Promote the scale-789 Q8 artifact to Sprint 47. The exact-call and intent gates pass, quantization preserves every observed BF16 output, and all provenance is pinned. Treat low-resolution score dimensions as uncertain inputs rather than exact facts; Sprint 48 must propagate their measured residuals. The fresh final holdout and combined 4 GB container remain championship gates, not reasons to keep Sprint 46 open.
