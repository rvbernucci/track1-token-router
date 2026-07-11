# Sprint 24 - Deterministic Solver Pack

## Type

Does not depend on credit.

## Objective

Expand guardrails to a pack of secure deterministic solvers, focused on mechanical tasks that do not need local LLM nor Fireworks.

## Why It Matters

If code resolves it with certainty, using an LLM is a waste of latency and risk. The solver pack increases accuracy in mechanical tasks and reduces pressure on the cascade.

## Deliverables

- Module `router/orchestration/solvers.py`.
- Registry of solvers with name, confidence, and reason.
- Secure solvers for simple math and transformations.
- False-positive tests.
- Savings metrics in the battle drill.
- Registry reused as candidate engine when `sub_intent` and regression indicate high `deterministic_fit`.

## Checklist

- [x] Create `SolverResult` contract.
- [x] Create registry of solvers.
- [x] Resolve safe addition, subtraction, multiplication, and integer division.
- [x] Resolve simple numerical comparison.
- [x] Resolve character count.
- [x] Resolve word count.
- [x] Resolve uppercase/lowercase/titlecase.
- [x] Resolve trim/normalize whitespace.
- [x] Resolve JSON compact when payload is valid.
- [x] Resolve JSON pretty when payload is valid.
- [x] Resolve extraction of first/last item from a simple list.
- [x] Block algebra, ambiguous dates, and word problems.
- [x] Add false-positive tests.
- [x] Add final format tests.
- [x] Measure routes saved in the battle drill.
- [x] Document limits of solvers.

## Acceptance Criteria

- Solvers only respond when confidence is high.
- Complex cases pass to the normal runner.
- The solver pack reduces cascade calls in mechanical tasks.
- The CI proves that we are not using regex as general reasoning.

## Expected Output

A real efficiency gain without depending on models, credit, or fragile heuristics.

## Decision

Each solver must be small, explicit, and tested. If the rule requires semantic interpretation, it does not belong to the deterministic solver.

## Evidence of Closure

- `python3 -m unittest tests.test_solvers tests.test_competition_mode tests.test_state_machine tests.test_battle_drill`: 25 focused tests passing.
- `ROUTER_MODE=competition COMPETITION_DRY_RUN=1 python3 -m router ask "What is 6 * 7? Return only the number." --json`: `solver_arithmetic` route, response `42`, zero remote tokens.
- `python3 scripts/battle_drill.py`: `solver_pack_ready=true`.
- Limits documented in `docs/DETERMINISTIC_SOLVERS.md`.
