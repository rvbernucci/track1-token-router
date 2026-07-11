# Sprint 57 - Ground Truth And Contract Adjudication

Status: **Completed - labels frozen behind sealed holdout firewall**

## Objective

Determine whether each frozen E2B candidate satisfies its task after safe Answer Contract normalization. Use mechanical evidence whenever possible and independent cross-provider judgment only where semantics cannot be proven locally.

## Label Contract

```text
raw_correct
contract_valid
normalization_changed
normalized_correct
hard_verifier_passed
judge_consensus
final_label = correct | incorrect | uncertain
```

For regression, only `correct` maps to `1`. Both `incorrect` and `uncertain` map to `0`. The Answer Contract Engine may normalize representation but may never repair semantic content.

## Deliverables

- Immutable raw-to-normalized candidate ledger.
- Mechanical oracle and verifier result per supported family.
- Cross-provider judge assignment with generator/judge separation.
- Adjudication queue for disagreement and ambiguity.
- Versioned final label policy with explicit evidence precedence.
- Per-category confusion and format-recovery report.
- Sealed final-holdout labels inaccessible to Sprint 58 fitting code.

## Checklist

### Answer Contract

- [x] Infer the requested shape from the original prompt only.
- [x] Preserve the raw E2B answer before any transformation.
- [x] Apply only unique, semantics-preserving normalization.
- [x] Record every transformation and rejection reason.
- [x] Score raw and normalized answers separately.
- [x] Reject ambiguous extraction, truncation and multiple-answer repairs.
- [x] Prove idempotence by applying normalization twice.

### Mechanical Evidence

- [x] Use proof-carrying math and logic before any LLM judge.
- [x] Execute supported code in the bounded sandbox.
- [x] Validate NER and context QA against exact source spans.
- [x] Require extractive grounding for locally verifiable summaries.
- [x] Require high-margin lexical/model agreement for sentiment.
- [x] Treat failed or unsupported verification as abstention, not correctness.
- [x] Store proof, execution or span evidence with stable hashes.

### Semantic Judgment

- [x] Send only mechanically unresolved rows to model judges.
- [x] Use at least two independent judge families per unresolved row.
- [x] Prevent a generator from being the sole judge of its own row.
- [x] Blind judges to route, model identity and competing answers.
- [x] Require structured verdict, confidence reason and format assessment.
- [x] Send disagreements to a separately assigned adjudicator.
- [x] Preserve `uncertain` when consensus cannot be established.

### Quality And Leakage

- [x] Measure judge agreement and disagreement by category.
- [x] Audit a stratified sample manually or with a third independent judge.
- [x] Detect answer leakage and reference-copy artifacts.
- [x] Keep final-holdout labels outside all fit and threshold commands.
- [x] Freeze label, evidence and judge-policy hashes.
- [x] Publish aggregate metrics without exposing sealed references.

## Metrics

- raw and normalized accuracy by category;
- format-only recovery rate;
- semantic-error rate after valid formatting;
- hard-verifier coverage and false-release count;
- judge agreement, disagreement and uncertain rates;
- generator/judge independence violations;
- Answer Contract idempotence and ambiguity failures;
- label counts by verifier family and split.

## Promotion Gate

- Zero semantic changes introduced by Answer Contract normalization.
- Zero hard-verifier-invalid candidates labeled correct.
- Zero rows judged solely by their generator.
- At least 95% agreement on the audited consensus sample.
- All disagreements are adjudicated or remain `uncertain`.
- Every label is traceable to mechanical evidence or independent judge records.
- Final-holdout labels remain sealed from all Sprint 58 code paths.

## Completion Contract

- Command: `python3 scripts/adjudicate_e2b_regression_v2.py --check`.
- Versioned artifact: `configs/e2b-regression-v2-label-policy.json`.
- Evidence report: `reports/generated/e2b-regression-v2-adjudication.md`.
- Decision record: freeze labels or reject contaminated/ambiguous cohorts.
- Dependency: consumes Sprint 56 frozen outputs; feeds Sprint 58.

## Anti-Scope

- Do not let normalization substitute a correct answer.
- Do not let E2B or FunctionGemma self-report correctness.
- Do not force judge disagreement into a binary positive label.
- Do not tune prompts after viewing final-holdout labels.
- Do not use remote-model eloquence as a correctness criterion.

## Completion Evidence

- Corpus: 2,000 frozen candidates, with 1,600 development rows and 400 physically sealed final-holdout rows.
- Labels: development `670 correct / 929 incorrect / 1 uncertain`; sealed final `158 correct / 242 incorrect`.
- Contract: 335 normalized representations, 297 invalid contracts and seven non-idempotent transformations quarantined.
- Verification: all registered proof, sandbox and grounding families were attempted before semantic judgment; unsupported or failed checks abstained.
- Judges: 833 unresolved pairs, 52 disagreements sent to an independent Codex adjudicator and 51 resolved (`98.08%`).
- Safety: nine invalid FunctionGemma assessments are pinned to direct Fireworks fallback and excluded from local fitting eligibility.
- Reproducibility: candidate, label and six judge-ledger SHA-256 hashes are frozen in `configs/e2b-regression-v2-label-policy.json`.
- Verification command: `python3 scripts/adjudicate_e2b_regression_v2.py --check` passes all gates.

## Promotion Decision

Freeze the development labels for Sprint 58 fitting. Keep the final-holdout labels sealed and inaccessible to all fitting and threshold-selection commands. Treat only `correct` as positive; both `incorrect` and `uncertain` are negative. Any missing or invalid FunctionGemma assessment bypasses both local regressions and routes directly to Fireworks.
