# FunctionGemma Dataset Pilot

Date: 2026-07-09
Rubric: `assessment-rubric-v2`
Assessment schema: `task-assessment-v1`

## Outcome

| Metric | Result |
|---|---:|
| Generated / validated / deduplicated | 120 / 120 / 120 |
| Duplicate rate | 0.00% |
| Accepted gold / unresolved | 120 / 0 |
| Rating records | 301 |
| Independent rater families | 3 |
| Terminal failures | 0 |
| Fireworks billable cost | $0.0192993 |
| Fireworks cost per accepted row | $0.0001608275 |
| Train / validation / private hidden | 104 / 16 / 24 |
| Rendered tokens min / p50 / p95 / max | 574 / 635 / 810 / 955 |

Rater families were Claude Sonnet 5 through Claude Code, Gemini 3.5 Flash Medium through Antigravity, and Minimax M3 through Fireworks. Raw inter-rater intent agreement was `0.9504`; sub-intent agreement was `0.7851`. The lower raw sub-intent and `deterministic_fit` agreement motivated evidence-backed adjudication and explicit mechanical-solver rules rather than silent averaging.

## Leakage Controls

- Hidden labels were authored and stored separately from teacher-provider requests.
- No normalized template family or mutation lineage crosses split boundaries.
- Related examples are assigned as connected components, not row-by-row.
- Public reporting contains no hidden prompt, hidden label, credential or raw provider response.

## Promotion Decision

Promote this pilot to the untuned baseline and first training experiment. Do not promote it directly as the championship dataset. Measure a learning curve and scale only when additional accepted rows improve held-out schema validity, intent/sub-intent accuracy, score MAE, weighted kappa and boundary ordering.

The measured maximum is below the pinned `1024` training context, so no accepted pilot row is truncated.

The reported agreement measures rater consistency, not model accuracy and not final label correctness.
