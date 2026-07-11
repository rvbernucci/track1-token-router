# Grounded Extraction And Classification

- gate: `True`
- fresh holdout rows: `129`
- verified zero-token releases: `60` (46.51%)
- false releases: `0`
- false refusals: `0`
- source-span precision: `100.00%`
- expected-evidence recall: `100.00%`
- estimated Fireworks calls avoided: `60`
- estimated Fireworks tokens avoided: `2480`
- verifier p95: `0.871 ms`

## Cohorts

| Cohort | Rows | Released | Correct releases | Correct refusals | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| context_qa | 23 | 8 | 8 | 15 | 100.00% | 100.00% |
| ner | 34 | 17 | 17 | 17 | 100.00% | 100.00% |
| sentiment | 47 | 22 | 22 | 25 | 100.00% | 100.00% |
| summary | 25 | 13 | 13 | 12 | 100.00% | 100.00% |

## Promotion Gate

- [x] `fresh_holdout_at_least_120_rows`
- [x] `zero_false_releases`
- [x] `all_promoted_references_released`
- [x] `every_family_precision_at_least_90_percent`
- [x] `every_family_has_at_least_eight_verified_releases`
- [x] `source_span_precision_100_percent`
- [x] `expected_evidence_recall_100_percent`
- [x] `zero_hallucinated_entity_releases`
- [x] `zero_context_contradiction_releases`
- [x] `zero_open_world_releases`
- [x] `zero_summary_factual_violations`
- [x] `sentiment_en_pt_precision_at_least_90_percent`
- [x] `p95_below_10_ms`
- [x] `batch_below_ten_minutes`

## Decision

Promote only typed/source-grounded NER, uniquely supported context QA, high-margin EN/PT sentiment with local-candidate agreement, and extractive summaries satisfying Answer Contract v2. Mixed or sarcastic sentiment, conflicting context, open-world facts, overlapping entities and abstractive summaries escalate.
