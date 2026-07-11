# Sprint 18 - Budget Manager & Token-Latency Governor

## Type

Does not depend on credit.

## Objective

Create a budget manager that controls estimated remote cost, actual remote cost, latency, and escalation limit per task.

## Why it matters

The goal of Track 1 is to get it right while spending little. Without a budget manager, the system might make correct decisions in isolation but still lose in the aggregate.

## Deliverables

- Module `router/orchestration/budget.py`.
- `TaskBudget` contract.
- `BudgetDecision` contract.
- Offline remote token estimator.
- Penalty for latency and parse failure.
- Integration with the offline scoreboard.
- Limit and edge case tests.

## Checklist

- [x] Define default budget per task.
- [x] Define global budget per run.
- [x] Estimate tokens before remote call.
- [x] Record actual tokens after remote call.
- [x] Create `allow_remote` decision.
- [x] Create `deny_remote_budget_exceeded` decision.
- [x] Create `deny_remote_latency_risk` decision.
- [x] Penalize parse failure in the budget.
- [x] Integrate with `offline_score_simulator.py`.
- [x] Add metrics in trace analytics.
- [x] Add token overflow tests.
- [x] Add latency overflow tests.

## Acceptance criteria

- The runner knows when it can no longer escalate.
- Remote cost is visible before and after the decision.
- Budget can be simulated without actual Fireworks.
- The scoreboard also starts comparing policies by budget discipline.

## Expected output

A cost governor that prevents the architecture from winning a task but losing the competition.

## Local evidence

```bash
python3 -m unittest tests.test_budget_manager
python3 scripts/offline_score_simulator.py
python3 scripts/analyze_traces.py --logs fixtures/logs/sample-run.jsonl
scripts/offline_release_check.sh
```

## Decision

The budget manager is born as a deterministic and offline module. It defines `allow_remote`, `deny_remote_budget_exceeded`, and `deny_remote_latency_risk` decisions, records actual spending, and injects a violation penalty into the scoreboard. The Sprint 19 policy engine starts consuming these signals to make better decisions.
