# Sprint 23 - Official Input Fuzz Pack

## Type

Does not depend on credits.

## Objective

Create a fuzzing pack to simulate input/output formats that may appear in the official evaluator, including free text, JSON, JSONL, files, large payloads, unicode, strict schemas, and broken cases.

## Why it matters

The biggest risk of the kickoff is not just the model, but the contract. If the official input is different from what we expect, the runner must fail gracefully or adapt quickly.

## Deliverables

- `evals/fuzz/tasks.jsonl`.
- `evals/fuzz/expected.jsonl`.
- Fixtures of attached files.
- Script `scripts/generate_fuzz_eval.py`.
- Script `scripts/run_fuzz_eval.py`.
- Report `reports/generated/fuzz-report.md`.
- Adapter and CLI tests against adversarial payloads.

## Checklist

- [x] Create cases with empty text.
- [x] Create cases with extreme whitespace.
- [x] Create cases with unicode and accents.
- [x] Create cases with multi-line input.
- [x] Create JSON cases with alternative fields.
- [x] Create JSONL cases with controlled invalid lines.
- [x] Create cases with a `.txt` file.
- [x] Create cases with a `.json` file.
- [x] Create cases with large payloads.
- [x] Create cases of `number only` responses.
- [x] Create cases of compact JSON responses.
- [x] Create cases of literal echo.
- [x] Create cases with prohibited markdown.
- [x] Validate that controlled errors go to `stderr`.
- [x] Validate that `stdout` does not receive debug logs.
- [x] Integrate fuzz report into the battle drill.

## Acceptance criteria

- The pack runs without credits.
- The runner does not break under strange formats.
- The report shows input classes and success rate.
- Parse failures are controlled and tested.

## Expected output

Fewer surprises at kickoff and a higher chance of adapting the official adapter in minutes, not hours.

## Decision

The fuzz pack must test contract and robustness, not deep semantic quality. It exists to protect the runner against unexpected formats.

## Closure evidence

- `python3 scripts/generate_fuzz_eval.py --check`: valid dataset and fixtures.
- `python3 scripts/run_fuzz_eval.py --check`: `contract_success=true`, 16 tasks, 15 classes, and full traces.
- `python3 -m unittest tests.test_fuzz_pack tests.test_battle_drill`: fuzz pack, controlled stderr, clean stdout, and battle drill integrated.
