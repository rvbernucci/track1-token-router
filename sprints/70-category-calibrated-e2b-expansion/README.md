# Sprint 70 - Category-Calibrated E2B Expansion

## Objective

Increase zero-Fireworks-token E2B coverage without weakening the Track 1 accuracy gate. Build a lineage-safe `2,400`-task expansion corpus, combine it with all eligible historical E2B evidence, enrich the router with production-available mechanical features, and promote an independently calibrated regression and threshold for each of the eight categories.

The sprint is accuracy-first. A category, cohort, or threshold that lacks sufficient evidence remains routed to Fireworks.

## Starting Evidence

- [x] Inventory `2,000` unique legacy E2B regression tasks.
- [x] Inventory `2,000` unique E2B regression V2 tasks.
- [x] Inventory `480` unique Sprint 65 boundary tasks.
- [x] Confirm `4,480` unique prompts across the three E2B evaluation populations.
- [x] Confirm `3,982` complete FunctionGemma/E2B outcome rows in the original `4,000`-task matrix population.
- [x] Recompute the complete-row count after adding the `480` boundary rows: `4,462` complete rows.
- [x] Produce a canonical ledger that distinguishes prompts, model runs, contract outputs, labels and regression-ready observations.
- [x] Prove that duplicated artifacts from inference, adjudication and reporting are not counted as new questions.

## Success Hypotheses

- [x] Factual QA showed high point precision (`9/10`) but insufficient sealed support; hypothesis observed and safely rejected for promotion.
- [x] Bounded summarization did not produce an accuracy-safe calibrated cohort; hypothesis rejected.
- [x] Short code generation did not produce an accuracy-safe calibrated cohort; hypothesis rejected.
- [x] Logic puzzles did not produce an accuracy-safe calibrated cohort; hypothesis rejected.
- [x] Category-specific calibration outperforms the v1 threshold on the full replay while exposing category-level failures.
- [x] Mechanical prompt features improved the nominated sentiment model and survived the sealed gate.
- [x] FunctionGemma retraining was unnecessary because score collapse did not remain after enrichment and calibration.

## Workstream 1 - Freeze the Experimental Protocol

- [x] Create a versioned experiment plan and manifest containing seed, provider allocation, category quotas, difficulty quotas and split policy.
- [x] Define exactly `8 categories x 3 difficulty bands x 100 tasks = 2,400 tasks`.
- [x] Allocate generation equally between Antigravity and Fireworks: `1,200` targets each.
- [x] Define `easy`, `moderate` and `hard` through observable construction rules, not subjective labels alone.
- [x] Require every task to be self-contained, stable, non-current and objectively judgeable.
- [x] Assign a unique semantic seed, template family and mutation lineage before generation.
- [x] Freeze final prompt hashes and make incremental inference invalidate stale prompt hashes after deduplication repairs.
- [x] Separate lineages, not individual rows, across fit, calibration and final holdout.
- [x] Reserve `20%` of new lineages as a sealed final holdout.
- [x] Prohibit tuning, feature selection or threshold selection against the sealed holdout.
- [x] Preserve append-only generation responses, candidates, checkpoints and a hash-pinned materialized manifest.

## Workstream 2 - Generate the 2,400-Task Corpus

- [x] Generate `100` easy, `100` moderate and `100` hard tasks for factual Q&A.
- [x] Generate `100` easy, `100` moderate and `100` hard tasks for math reasoning.
- [x] Generate `100` easy, `100` moderate and `100` hard tasks for sentiment.
- [x] Generate `100` easy, `100` moderate and `100` hard tasks for summarization.
- [x] Generate `100` easy, `100` moderate and `100` hard tasks for NER.
- [x] Generate `100` easy, `100` moderate and `100` hard tasks for code debugging.
- [x] Generate `100` easy, `100` moderate and `100` hard tasks for logic puzzles.
- [x] Generate `100` easy, `100` moderate and `100` hard tasks for code generation.
- [x] Alternate providers by independent lineage.
- [x] Store provider, model, request ID, usage, estimated cost and generation timestamp.
- [x] Enforce a Fireworks spending ceiling; final generation cost was `$3.1369353`.
- [x] Checkpoint after every successful generation batch.
- [x] Retry only failed or explicitly deduplicated target IDs; never regenerate successful IDs silently.
- [x] Reject ambiguous, time-sensitive, unsafe, unverifiable or over-context tasks.
- [x] Reject exact, normalized and semantic near-duplicates against all `4,480` existing prompts.
- [x] Reject cross-split template and lineage leakage.
- [x] Publish aggregate provenance while keeping credentials and sealed references out of Git.

## Workstream 3 - Mechanical Feature Engine

All features must be computable from the incoming prompt before choosing a route. No gold answer, E2B answer, judge result or declared dataset difficulty may enter the runtime feature vector.

- [x] Add prompt character count, word count and deterministic token estimate.
- [x] Add detected language and language-indicator features.
- [x] Add requested output shape: label, number, short text, free text, JSON or code.
- [x] Add explicit answer-length and sentence-count constraints.
- [x] Add source-text length for summarization and grounded tasks.
- [x] Add code presence, detected programming language and code-line count.
- [x] Add code complexity proxies: branch count and loop count; syntax remains a post-response verifier signal.
- [x] Add numeric density, operator count and variable count.
- [x] Add requested-entity-type features for NER.
- [x] Add negation, ambiguity, temporal/currentness and external-knowledge indicators.
- [x] Add strict-format and prompt-injection indicators.
- [x] Add pre-route deterministic-verifier availability indicators for numeric, closed-label, JSON-structure and code-syntax families.
- [x] Keep verifier outcomes out of the pre-route E2B regression unless that outcome exists before routing.
- [x] Normalize continuous features with per-intent mean and scale learned from fit rows only and persisted in the policy artifact.
- [x] Version the feature schema and reject unknown or non-finite values fail-closed.
- [x] Unit-test features against positive, negative, Unicode and adversarial fixtures.

## Workstream 4 - Production-Matched Local Inference

- [x] Confirm the available local runtime and use the exact CPU profile required by the submitted `4 GB / 2 vCPU` environment; RTX 4060 execution was not required.
- [x] Pin the exact FunctionGemma Q8 and text-only E2B artifacts used by the submitted image.
- [x] Verify FunctionGemma and E2B artifact hashes before inference.
- [x] Run FunctionGemma on raw prompts only and capture intent plus five calibrated scores for `2,383/2,400` valid rows.
- [x] Route the `17` invalid FunctionGemma outputs directly to Fireworks and exclude them from fitting.
- [x] Run E2B on all `2,400` prompts at the production `96`-token ceiling with zero inference failures.
- [x] Preserve raw E2B output separately from the final answer.
- [x] Apply the exact production Answer Contract Engine after E2B inference.
- [x] Record contract validity, safe repairs and final post-contract output.
- [x] Record latency, timeout, runtime profile and runtime failure separately from semantic correctness; memory pressure is covered by the exact-image resource gate.
- [x] Make inference resumable and idempotent by task ID, prompt hash and artifact hash.
- [x] Compare a deterministic sample across the exact two-thread runtime and the higher-throughput four-thread runtime; all `10/10` outputs were byte-identical, so final inference uses the official two-thread profile.
- [x] Never count a timeout, missing output, invalid assessment or contract failure as correct.

## Workstream 5 - Independent Adjudication

- [x] Use exact or mechanical validators wherever correctness can be established without an LLM judge.
- [x] Use sandboxed syntax/AST checks for supported code tasks without executing untrusted code on the host.
- [x] Use numeric normalization and tolerance rules only when the task explicitly permits them.
- [x] Use structured-set comparison for NER when ordering is not semantically relevant.
- [x] Use reference-grounded criteria for summarization rather than lexical similarity alone.
- [x] Send only non-mechanical cases to independent judges.
- [x] Prevent the task generator from being the sole judge of its own examples.
- [x] Blind judges to provider, declared difficulty, FunctionGemma scores, route probability and E2B identity.
- [x] Require two independent judgments for semantic cases.
- [x] Send all disagreements to a third adjudicator; final unresolved count is zero.
- [x] Exclude unresolved labels from fitting and count them as failures in conservative runtime simulations.
- [x] Store raw answer, post-contract answer, validator evidence and final binary label.
- [x] Audit `241/2,400` labels, including at least `10%` of mechanical and judge strata, with a model different from the generator.
- [x] Report agreement, disagreement and label source by category and difficulty; independent judge-pair agreement is `97.00%`.

## Workstream 6 - Canonical Regression Ledger

- [x] Join every eligible observation by immutable task ID and prompt hash.
- [x] Preserve source population: legacy, V2, boundary or expansion.
- [x] Preserve split role and mutation lineage.
- [x] Include FunctionGemma intent and five scores.
- [x] Include only production-available mechanical features.
- [x] Include E2B contract status and binary post-contract correctness; raw runtime status remains in the traceable inference ledger.
- [x] Record missingness explicitly rather than imputing silently.
- [x] Route invalid FunctionGemma assessments to Fireworks and exclude them from E2B model fitting.
- [x] Deduplicate by normalized prompt and semantic lineage before fitting.
- [x] Generate a schema-validated `6,845`-row deterministic ledger with SHA-256 `b55205f4...e0d7`.
- [x] Report unique prompts, complete rows, positive labels and negative labels by source and category.
- [x] Keep original historical split roles where available.
- [x] Prevent old sealed holdouts from becoming both training and claimed independent evidence.

## Workstream 7 - Per-Category Matrix Models

- [x] Fit one regularized logistic baseline per category using only the five FunctionGemma scores.
- [x] Fit one enriched regularized logistic model per category using scores plus mechanical features.
- [x] Compare ridge, elastic-net and constrained quadratic logistic challengers.
- [x] Prefer ridge as the simplest model when discrimination and calibration are statistically comparable.
- [x] Handle class imbalance through weighting inside fit folds, not by altering holdout prevalence.
- [x] Group cross-validation by semantic lineage and source population.
- [x] Ensure zero lineage overlap between train and held-out folds.
- [x] Produce out-of-fold probabilities for every eligible development row.
- [x] Compare score-only versus enriched models using Brier score, log loss, AUROC and average precision.
- [x] Measure score-only versus enriched feature ablations.
- [x] Measure performance separately by category, difficulty, provider, language, output shape and source population.
- [x] Reject operating points with any supported provider, difficulty, source, language or output-shape slice below `75%` precision.
- [x] Quantify train-serving skew between historical and expansion populations.
- [x] Persist coefficients, normalization statistics, feature order and schema version.

## Workstream 8 - Independent Calibrator per Category

- [x] Fit calibration only on the designated calibration split using fit-trained model scores.
- [x] Compare Platt scaling and isotonic regression when sample support permits.
- [x] Fall back to a remote-only threshold when a calibrator is under-supported.
- [x] Select a distinct E2B decision threshold for each category.
- [x] Optimize for the largest coverage subject to the accuracy-first precision floor and subgroup safety.
- [x] Calculate precision, coverage, false-positive rate and Wilson 95% lower bound at every candidate threshold.
- [x] Require minimum selected support before promoting a category or sub-cohort.
- [x] Keep thresholds bounded in `[0, 1]` and deterministic for a frozen calibration set.
- [x] Persist `thresholds_by_intent` instead of relying on one global `decision_threshold`.
- [x] Preserve a global emergency threshold of `1.0` as a fail-closed compatibility fallback.
- [x] Route missing calibrators, unknown intents and non-finite probabilities to Fireworks.

## Workstream 9 - Promotion Gates

- [x] Require at least `20` independently held-out selected examples plus a Wilson 95% lower bound of `75%`; this gate was frozen before opening the `60`-row-per-category holdout because a `50`-row minimum would force `83.3%` coverage and invalidate selective routing.
- [x] Require held-out precision of at least `85%` for ordinary E2B cohorts.
- [x] Require Wilson 95% lower bound of at least `75%` for promoted cohorts.
- [x] Require no promoted difficulty band with precision below `75%` when support is at least `20`.
- [x] Require calibration error and Brier score not to regress materially against the score-only baseline.
- [x] Require enriched features to improve coverage at the same precision or precision at the same coverage.
- [x] Require zero invalid FunctionGemma assessments routed to E2B.
- [x] Require zero runtime or Answer Contract Engine failures released as final local answers.
- [x] Require deterministic and Fireworks fallbacks to remain unchanged for rejected rows.
- [x] Keep factual QA and NER disabled despite high point precision because selected support was insufficient.
- [x] Treat prior `60/60` results as cohort evidence, not proof that an entire category is safe.
- [x] Evaluate decision-surface SHA-256 `76e7e60f...3fe4` once on the sealed final holdout.
- [x] Do not retune after opening the sealed holdout; only the non-decision metadata hash scope was corrected and fully audited.

## Workstream 10 - Runtime Integration

- [x] Introduce a backward-compatible matrix-policy schema containing per-category models, calibrators and thresholds.
- [x] Validate artifact schema, dimensions, hashes, finite coefficients and allowed intents at startup.
- [x] Compute mechanical features deterministically before E2B route selection.
- [x] Apply the model and calibrator corresponding to FunctionGemma's predicted intent.
- [x] Attach probability, threshold, feature-schema version and decision reason to routing traces.
- [x] Fail closed to Fireworks on missing artifacts, feature errors, unknown categories or invalid probabilities.
- [x] Preserve the deterministic solver as the first route where it can produce a recomputable proof.
- [x] Preserve E2B as the second route and Fireworks as the safe fallback.
- [x] Add migration tests for the current v1 policy and the new per-category policy.
- [x] Add golden tests that prove different categories can use different thresholds.
- [x] Add tests proving no declared difficulty, gold answer or judge field reaches runtime features.
- [x] Rebuild and test the exact `linux/amd64` image under `4 GB RAM`, `2 vCPU`, no network and ten-minute limits; release run `29178529654` passed.
- [x] Confirm both local model artifacts remain embedded and hash-correct with no startup download; exact-image run `29179000266` passed.
- [x] Confirm compressed image size `2,666,318,316` bytes remains below `10 GB`.

## Workstream 11 - Championship Simulation

- [x] Replay all eligible historical development rows through the candidate router.
- [x] Replay the new calibration split through the candidate router.
- [x] Run the sealed expansion holdout exactly once after policy freeze.
- [x] Simulate factual-heavy, summarization-heavy, code-heavy, logic-heavy and uniform distributions.
- [x] Measure local E2B and Fireworks-fallback route shares; deterministic evidence remains unchanged from the prior image.
- [x] Measure local precision, estimated Fireworks input tokens avoided and failures without inventing remote correctness or output-token values absent from this ledger.
- [x] Compare against the previously promoted sentiment-only policy.
- [x] Report higher replay precision (`88.41%` versus `83.58%`) and higher zero-token coverage (`8.82%` versus `7.74%`).
- [x] Report category and distribution cuts rather than only global averages.
- [x] Produce a counterexample queue for every promoted category.
- [x] Keep every failed category remote automatically; factual QA and NER were rolled back by the promotion gate.

## FunctionGemma Retraining Decision

- [x] Measure score cardinality and entropy per category before retraining.
- [x] Measure how often distinct prompt structures collapse to identical five-score vectors.
- [x] Measure enriched-regression performance while keeping FunctionGemma frozen on historical fit/calibration rows.
- [x] Retrain FunctionGemma only if score collapse remains a demonstrated bottleneck; historical evidence does not currently justify retraining.
- [x] Close the contrastive-retraining branch as not triggered because score collapse was not the demonstrated bottleneck.
- [x] Keep the frozen FunctionGemma training data disjoint from E2B sealed holdout lineages.
- [x] Preserve the promoted FunctionGemma schema, intent and score gates because no retraining occurred.
- [x] Retain the existing Q8 artifact rather than risk structured-output reliability without evidence.

## Resource and Budget Controls

- [x] Use CPU for generation orchestration, feature extraction, regression and calibration.
- [x] Do not use the RTX 4060 because production-matched CPU inference was available and retraining was not justified.
- [x] Pin maximum Fireworks generation and adjudication budgets separately.
- [x] Prefer mechanical validation before paid judge calls.
- [x] Use Antigravity for its allocated generation lineages while account and quota checks pass.
- [x] Stop rather than silently switching provider, account or model.
- [x] Record estimated and billable provider cost in generation state and the final manifest.
- [x] Make generation and local inference resumable after interruption.

## Required Evidence

- [x] `evals/e2b-expansion-v1/manifest.json`
- [x] `evals/e2b-expansion-v1/plan.jsonl`
- [x] `evals/e2b-expansion-v1/splits/train.jsonl`
- [x] `evals/e2b-expansion-v1/splits/calibration.jsonl`
- [x] `evals/e2b-expansion-v1/sealed/tasks/final_holdout.jsonl` and separately protected references
- [x] `reports/generated/e2b-expansion-v1/functiongemma.jsonl`
- [x] `reports/generated/e2b-expansion-v1/e2b-raw.jsonl`
- [x] `reports/generated/e2b-expansion-v1/e2b-post-contract.jsonl`
- [x] `reports/generated/e2b-expansion-v1/labels.jsonl`
- [x] `reports/generated/e2b-expansion-v1/regression-ledger.jsonl`
- [x] `configs/e2b-category-matrix-regression-v2.json`
- [x] `reports/public/e2b-category-calibration-v2.md`
- [x] `reports/public/e2b-category-calibration-v2.json`
- [x] `reports/public/e2b-expansion-championship-scorecard.md`

## Definition of Done

- [x] Exactly `2,400` valid new tasks exist with `300` per category and `100` per difficulty band.
- [x] No exact, normalized, semantic or lineage leakage exists across protected splits.
- [x] Every eligible regression row has traceable prompt, FunctionGemma assessment, E2B output, contract result and correctness evidence.
- [x] Every runtime feature is available before route selection.
- [x] Eight independent category models and calibrators are evaluated, even though seven remain disabled.
- [x] Sentiment, the only enabled category, passes support, precision, Wilson, calibration, subgroup and runtime-safety gates.
- [x] The new router improves replay precision and zero-token coverage over the previous policy.
- [x] The final Docker image passes the official input/output, resource, architecture, network, local-inference and size gates.
- [x] Public documentation reports both gains and failed hypotheses without overstating hidden-evaluation performance.
- [x] Promotion is reversible through one hash-pinned configuration artifact; `v3.5.0-full-hybrid` remains the image rollback.

## Completion Decision

Status: **complete**.

The sprint is complete only after a frozen candidate policy passes the sealed holdout and exact-image championship simulation. Corpus generation or a higher development-set accuracy alone is not sufficient for promotion.
