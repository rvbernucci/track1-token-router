# Sprint 22 - Competition Mode Integration

## Type

Does not depend on credit.

## Objective

Create a single competition mode that integrates guardrails, state machine, risk signals, budget manager, policy engine, prompt packet, final validator, and battle trace into a coherent operational path.

## Why It Matters

Sprints 17-21 created strong pieces. To compete seriously, these pieces need to become a plug-and-play execution mode with predictable behavior configurable by env vars.

## Deliverables

- `ROUTER_MODE=competition`.
- Runner `CompetitionRunner` or equivalent wrapper.
- Single-decision contract per task.
- Consolidated trace with policy, budget, validation, and route.
- Dry-run mode without real providers.
- Offline comparison between `competition` and legacy modes.
- End-to-end tests in CLI and JSONL.

## Checklist

- [x] Define `CompetitionDecision` contract.
- [x] Define `CompetitionTrace` contract.
- [x] Create `CompetitionRunner`.
- [x] Enable guardrails as step zero.
- [x] Enable risk signals before decision.
- [x] Enable budget decision before any remote call.
- [x] Enable policy engine in the hot path.
- [x] Enable final validator always before output.
- [x] Record `final_answer_repaired` when there is a secure repair.
- [x] Record `remote_packet_tokens` in the trace.
- [x] Create env var `ROUTER_MODE=competition`.
- [x] Create dry-run that does not call a real model.
- [x] Add CLI `ask` test.
- [x] Add JSONL `run` test.
- [x] Add clean stdout test.
- [x] Update battle drill to include `competition` mode.

## Acceptance Criteria

- A single command executes the competition mode without credits.
- Competition mode generates clean final response on `stdout`.
- Trace includes policy, budget, final validation, and route.
- Legacy mode continues passing in CI.
- Battle drill compares competition mode against the baseline.

## Expected Output

The project stops being a set of labs and moves to a single competitive path, ready to receive real endpoints.

## Decision

Competition mode must be opt-in until it proves an advantage in the battle drill. This protects the current path while we mature the final runtime.

## Evidence of Closure

- `python3 -m unittest discover -s tests`: 101 tests passing.
- `python3 scripts/battle_drill.py`: `competition_mode_ready=true`.
- `ROUTER_MODE=competition COMPETITION_DRY_RUN=1 python3 -m router ask "What is 10 + 5? Return only the number."`: clean stdout with `15`.
