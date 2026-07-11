# Sprint 41 - Domain Correlation Eval Pack

## Type

Does not depend on credit.

## Objective

Create an offline evaluation pack to test if the task-model correlation matrix is classifying the right domains and excluding bad strategies.

## Thesis

The correlation matrix only has value if it is falsifiable. We need prompts by domain with a clear routing expectation, not just loose examples.

## Deliverables

- `evals/fireworks-pareto/domain-correlation.jsonl`.
- Fixture with `input`, `expected_domain`, `expected_tier`, `expected_allowed_pool`, `forbidden_models`.
- Script `scripts/eval_fireworks_pareto.py`.
- Report `reports/generated/fireworks-pareto-correlation-report.md`.
- Unit tests for minimum dataset coverage.

## Checklist

- [ ] Create 10 prompts per domain: cheap, medium, strong-code, strong-math, long-context, factual/current, formatting, extraction.
- [ ] Define `expected_domain` and `expected_tier` for each prompt.
- [ ] Define forbidden models: embedding, reranker, underqualified, over-expensive when applicable.
- [ ] Implement offline replay script using `select_fireworks_model`.
- [ ] Generate confusion matrix of expected domain vs. routed domain.
- [ ] Generate ranking of selected models by category.
- [ ] Add test ensuring that the dataset is parseable.
- [ ] Add test with minimum match rate per domain.

## Metrics

- domain match rate;
- tier match rate;
- forbidden model violations;
- model distribution by domain;
- underqualification rate;
- over-escalation rate.

## Definition of Done

- The eval runs without Fireworks.
- The report shows where the matrix is succeeding and failing.
- No auxiliary model wins the final response.
- Failures become concrete tuning tasks.

## Anti-Scope

- Do not call real API.
- Do not use LLM as judge in this sprint.
- Do not optimize weights before having a baseline.
