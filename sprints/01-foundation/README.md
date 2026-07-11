# Sprint 01 - Foundation and contracts

## Objective

Create the project's backbone: minimal CLI, input/output contracts, structured logs, and a testable skeleton.

This sprint does not attempt to win the hackathon yet. It prevents us from getting lost when kickoff reveals the actual format of the tasks.

## Deliverables

- Locally installable Python package.
- CLI with empty or semi-functional commands: `ask`, `solve`, `run`, `eval`.
- `TaskEnvelope`, `AnswerResult`, `RouteDecision`, and `TokenUsage` contracts.
- JSONL logger per task.
- Config via env vars.
- Unit tests for contracts and parsers.

## Checklist

- [x] Create `pyproject.toml`.
- [x] Create `router` package.
- [x] Create `router.core.contracts` module.
- [x] Create `router.cli.main` module.
- [x] Define input schema for plain text.
- [x] Define input schema for JSON.
- [x] Define input schema for JSONL.
- [x] Ensure that `stdout` only prints the final response.
- [x] Ensure that human logs go to `stderr`.
- [x] Create JSONL logger in `logs/run.jsonl`.
- [x] Create serialization and deserialization tests.
- [x] Document minimal env vars.

## Acceptance criteria

- [x] `router ask "What is 2+2?"` returns a mocked response on `stdout`.
- [x] `router solve --json < task.json` parses the envelope and returns final JSON.
- [x] `router run --jsonl tasks.jsonl --out output.jsonl` processes multiple tasks.
- [x] No debug log contaminates `stdout`.
- [x] Tests pass locally.

## Evidence

- `python3 -m unittest discover -s tests`
- `python3 -m router ask "What is 2+2?"`
- `python3 -m router solve --json`
- `python3 -m router run --jsonl tasks.jsonl --out output.jsonl`

## Technical decisions

- Python will be the competitive core.
- CLI-first, no web server at this stage.
- Structure oriented around contracts, not a framework.
- Everything that can vary at kickoff should come via adapter.

## Risks

- Overengineering before knowing the evaluator.
- Mixing internal format with final format.
- Creating a pretty CLI, but difficult to run in the container.

## Expected sprint output

A runner that is still basic, but reliable. From here on, any intelligence goes behind stable contracts.
