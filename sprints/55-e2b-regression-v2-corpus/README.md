# Sprint 55 - E2B Regression V2 Corpus

Status: **Completed - no AMD notebook required**

## Objective

Forge 2,000 new Track 1 tasks with independent template lineages, frozen references and provider provenance. The corpus must measure whether the exact local E2B runtime can produce a releasable answer, not whether E2B is better than a remote teacher.

## Fixed Population

| Split | Rows per category | Total rows | Permitted use |
|---|---:|---:|---|
| train | 150 | 1,200 | fit coefficients |
| validation | 50 | 400 | model and threshold selection |
| final holdout | 50 | 400 | one promotion decision only |
| total | 250 | 2,000 | all eight Track 1 categories |

The split assignment is created before FunctionGemma, E2B or judge inference. Template family, mutation lineage and semantic seed must be disjoint across splits.

## Deliverables

- Versioned corpus specification and deterministic generation seed.
- Append-only prompt and reference stores with provider provenance.
- Balanced Antigravity and Fireworks generation plan.
- Cross-provider role assignment that prevents generator self-judging.
- Lineage-aware deduplication and contamination audit.
- Separate runtime inputs and sealed references for the final holdout.
- Hash manifest for every split before local inference begins.

## Checklist

### Task Design

- [x] Generate exactly 250 rows for each official category.
- [x] Cover short, long, strict-format and adversarially phrased prompts.
- [x] Include at least 25% boundary cases targeting known E2B failures.
- [x] Include at least 20% output-contract variations.
- [x] Cover both mechanically verifiable and semantic-only tasks.
- [x] Preserve the official input contract: `task_id` plus raw `prompt`.
- [x] Never embed route labels, model names or expected difficulty in prompts.

### Provider Governance

- [x] Pin every generator provider, model and prompt-template hash.
- [x] Balance Antigravity and Fireworks generation by category and split.
- [x] Record provider request ID, token usage, timestamp and retry lineage.
- [x] Prevent a model from being the sole judge of a row it generated.
- [x] Keep API keys in runtime environment variables only.
- [x] Enforce append-only checkpoints and a fixed provider budget ledger.
- [x] Treat provider failure as missing data, never as a negative label.

### Split And Leakage Firewall

- [x] Assign split before any model output or correctness label exists.
- [x] Group paraphrases, mutations and shared references into one lineage.
- [x] Reject exact and near duplicates across split boundaries.
- [x] Prevent prior 1,991-task and Sprint 53 holdouts from entering the new final holdout.
- [x] Permit prior data for development only after lineage deduplication.
- [x] Store final references outside every runtime input file.
- [x] Freeze input, reference, lineage-map and manifest SHA-256 hashes.

### Corpus QA

- [x] Validate unique task IDs and non-empty prompts.
- [x] Validate category and requested-output-shape coverage.
- [x] Audit reference answer determinism and ambiguity.
- [x] Quarantine current/private factual questions without verifiable references.
- [x] Run prompt-injection and orchestration-leak scans.
- [x] Publish aggregate counts without publishing the sealed holdout answers.

## Completion Evidence

- Corpus: 2,000 rows, 1,000 mutation lineages, 250 rows per category.
- Splits: 1,200 train, 400 validation and 400 sealed final holdout.
- Providers: 1,000 Antigravity and 1,000 Fireworks assignments.
- Fireworks billable generation cost: US$ 1.6060476.
- Deduplication: zero exact and zero near-duplicate cross-lineage prompts after append-only selective retries.
- Verification: `python3 scripts/generate_e2b_regression_v2_corpus.py --check` passed with 10 hash-pinned artifacts.
- Regression suite: 570 tests passed.

## Metrics

- exact rows and categories by split;
- independent lineage and template counts;
- cross-split duplicate and near-duplicate rate;
- provider/category balance;
- output-shape and adversarial-format coverage;
- ambiguous or quarantined reference rate;
- generation cost, tokens and retry rate;
- sealed-reference exposure count.

## Promotion Gate

- Exactly 2,000 valid rows and 250 rows per category.
- Zero template, mutation-lineage or semantic-seed overlap across splits.
- Zero sealed answer fields in runtime input files.
- Zero generator self-judged rows without independent confirmation.
- Every artifact is hash-pinned and reproducible from the frozen seed.
- At least 100 independent development lineages for every candidate verifier family.

## Completion Contract

- Command: `python3 scripts/generate_e2b_regression_v2_corpus.py --check`.
- Versioned artifact: `configs/e2b-regression-v2-corpus.json`.
- Evidence report: `reports/generated/e2b-regression-v2-corpus.md`.
- Decision record: freeze the corpus or reject and regenerate it before inference.
- Dependency: consumes Track 1 taxonomy and Answer Contract v2; feeds Sprint 56.

## Anti-Scope

- Do not fit a router in this sprint.
- Do not inspect final-holdout E2B outcomes.
- Do not use model confidence as ground truth.
- Do not count paraphrases as independent evidence.
- Do not optimize the corpus against Kimi-specific behavior.
