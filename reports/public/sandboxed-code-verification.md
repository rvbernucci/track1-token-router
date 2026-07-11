# Sandboxed Code Verification

- gate: `True`
- holdout rows: `49`
- verified local releases: `18`
- mutation score: `100.00%`
- adversarial containment: `100.00%`
- false accepts: `0`
- false rejects: `0`
- repeatability: `100.00%`
- latency p95: `44.94 ms`
- peak verifier worker RSS: `13.19 MiB`

## Families

| Family | Rows | Accepted | Correct accept | Correct reject | False accept | False reject |
|---|---:|---:|---:|---:|---:|---:|
| add | 14 | 3 | 3 | 11 | 0 | 0 |
| max_list | 8 | 4 | 4 | 4 | 0 | 0 |
| normalize_slug | 5 | 2 | 2 | 3 | 0 | 0 |
| palindrome | 5 | 2 | 2 | 3 | 0 | 0 |
| second_largest | 6 | 2 | 2 | 4 | 0 | 0 |
| square | 6 | 3 | 3 | 3 | 0 | 0 |
| unique_preserve_order | 5 | 2 | 2 | 3 | 0 | 0 |

## Promotion Gate

- [x] `all_reference_candidates_accepted`
- [x] `zero_false_accepts`
- [x] `mutation_score_at_least_90_percent`
- [x] `all_adversarial_programs_contained`
- [x] `deterministic_repeatability`
- [x] `p95_below_250_ms`
- [x] `peak_rss_below_256_mib`
- [x] `batch_below_ten_minutes`

## Decision

Promote only the seven explicitly supported Python families. Unknown behavior, ambiguous contracts, unsupported languages and any static or dynamic failure remain Fireworks-only. An LLM review can add evidence but cannot override a failed executable gate.
