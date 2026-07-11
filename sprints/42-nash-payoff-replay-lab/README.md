# Sprint 42 - Nash Payoff Replay Lab

## Type

Does not depend on credit.

## Objective

Build a replay lab to compare selection strategies: pure lowest cost, old Pareto, Nash welfare, conservative-quality, and expected oracle per fixture.

## Thesis

It is not enough for Nash to look elegant. We need to prove that it improves the tradeoff against simple baselines and that it does not create regression in cheap tasks.

## Deliverables

- `scripts/replay_model_selection_strategies.py`.
- Baselines: `cheapest`, `pareto_cost_first`, `nash_welfare`, `quality_first`.
- `reports/generated/nash-payoff-replay.md` report.
- Payoff table per strategy.
- Regression tests for critical scenarios.

## Checklist

- [ ] Extract candidates and scores without calling Fireworks.
- [ ] Implement replay of the `cheapest` strategy.
- [ ] Implement replay of the `pareto_cost_first` strategy.
- [ ] Implement replay of the `nash_welfare` strategy.
- [ ] Implement replay of the `quality_first` strategy.
- [ ] Compare total estimated cost per strategy.
- [ ] Compare accuracy proxy violations per strategy.
- [ ] Compare over-escalation per strategy.
- [ ] Create Markdown report with table and conclusion.
- [ ] Add test to ensure `nash_welfare` does not choose an underqualified candidate.

## Metrics

- estimated total cost;
- expected accuracy proxy;
- over-escalation count;
- underqualification count;
- average Nash product;
- average prisoner's payoff;
- models chosen per domain.

## Definition of Done

- We have offline evidence of when Nash wins or loses.
- Simple baselines become reproducible.
- Strategy selection regression becomes an automated test.
- Report points to objective weight adjustments.

## Out of Scope

- Do not automatically tune weights in a loop yet.
- Do not treat results without fixtures as truth.
- Do not replace existing tests with a report.
