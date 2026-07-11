# Sprint 52 - Grounded Extraction And Classification

Status: **Completed - promoted by independent cohort gates**

## Objective

Expand zero-token verification for NER, context-bound factual Q&A, constrained summarization and high-margin sentiment. These families can be validated through source grounding even when they cannot be fully solved mechanically.

## Thesis

- Every extracted entity, quote, number and date should be traceable to a source span.
- Context-bound factual answers can be released when the answer is uniquely supported by the supplied text.
- Sentiment is locally safe only at high lexical/model agreement margins.
- Summary format can be proven mechanically; semantic completeness requires grounding checks and conservative escalation.

## Deliverables

- Source-span contract with offsets, normalized value and evidence text.
- Typed NER schema/cardinality verifier.
- Context-QA unique-support verifier.
- Numeric/entity preservation checks for summaries.
- Calibrated sentiment agreement gate combining lexicon, E2B and negation/contrast analysis.
- Multilingual and adversarial extraction corpus.
- Cohort report measuring local precision by extraction/classification subtype.

## Checklist

### NER

- [x] Require every entity value to map to one or more exact source spans.
- [x] Validate requested keys, types and scalar/list cardinality.
- [x] Normalize dates and numbers without losing original evidence.
- [x] Detect duplicate, overlapping and hallucinated entities.
- [x] Handle zero-entity cases explicitly.
- [x] Escalate ambiguous entity roles instead of guessing.

### Context-Bound Factual QA

- [x] Detect explicit context-only instructions.
- [x] Extract candidate evidence windows before answering.
- [x] Require unique support for scalar answers.
- [x] Detect conflicting mentions and “not present” cases.
- [x] Block current/open-world factual questions from deterministic release.
- [x] Preserve units, qualifiers and negation.

### Sentiment

- [x] Add aspect-target isolation.
- [x] Handle negation, contrast and intensifiers.
- [x] Compute lexical margin and disagreement signals.
- [x] Release only when E2B and high-margin deterministic classification agree.
- [x] Escalate mixed, sarcastic and implicit sentiment.
- [x] Calibrate separately by language.

### Summarization

- [x] Verify exact/max words, sentences and bullet counts.
- [x] Check that named entities and critical numbers are source-grounded.
- [x] Detect unsupported facts and dropped required terms.
- [x] Support extractive-summary proofs where the answer is a source span.
- [x] Escalate abstractive summaries without adequate grounding evidence.

## Metrics

- grounded-span precision/recall;
- hallucinated-entity release count;
- unique-support coverage for context QA;
- sentiment precision by margin and language;
- summary factual-consistency violations;
- local coverage by hidden-input mix scenario;
- Fireworks tokens saved per 100 tasks.

## Promotion Gate

- Zero released entities absent from the source on fresh adversarial tests.
- At least 90% local precision for promoted NER and sentiment cohorts.
- Context-QA release requires unique evidence and passes contradiction tests.
- Summary releases preserve every required entity/number and satisfy Answer Contract v2.
- Factual open-world questions always escalate.

## Completion Contract

- Planned command: `python3 scripts/evaluate_grounded_local_verifiers.py --check`.
- Versioned artifact: `configs/grounded-verifier-policy-v1.json`.
- Evidence report: `reports/generated/grounded-extraction-classification.md`.
- Decision record: promote NER, context-QA, sentiment and summary cohorts separately; no aggregate score can hide a weak cohort.
- Dependency: can run beside Sprints 50-51; exports grounding and margin features to Sprint 53.

## Anti-Scope

- Do not build a general knowledge base.
- Do not use embedding similarity as proof of factual support.
- Do not release sarcasm or mixed sentiment from lexicons alone.
- Do not truncate summaries mechanically to force compliance.

## Completion Evidence

- Command: `python3 scripts/generate_grounded_verifier_holdout.py && python3 scripts/evaluate_grounded_local_verifiers.py --check`.
- Holdout: 129 fresh multilingual/adversarial rows, including embedded source-instruction attacks and explicit abstractive-summary traps.
- Result: 60/60 valid candidates released, 69/69 unsafe or unsupported candidates refused, zero false releases in every cohort.
- Grounding: 114/114 released spans have exact offsets and 64/64 expected evidence items were recalled.
- Coverage: 46.51% of the mixed holdout released locally, avoiding an estimated 60 Fireworks calls and 2,480 tokens.
- Runtime: below 0.5 ms p95 and below 30 ms for the complete holdout on the development machine.
- Evidence: `reports/generated/grounded-verifier-evaluation.json` and `reports/generated/grounded-extraction-classification.md`.
- Policy: `configs/grounded-verifier-policy-v1.json` pins dataset/engine hashes and `tests/test_grounded_verifier.py` enforces anti-drift.

## Promotion Decision

Promote typed/source-grounded NER, uniquely supported context QA, high-margin English and Portuguese sentiment when the local candidate agrees, and strictly extractive summaries that satisfy Answer Contract v2. Keep open-world facts, conflicting support, ambiguous or overlapping entities, low-margin/mixed/sarcastic sentiment and abstractive summaries on Fireworks. Source text is isolated before output-contract inference so prompt content cannot redefine the answer format.
