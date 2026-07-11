# Sprint 09 - Official Adapter Readiness

## Type

Does not depend on credit.

## Objective

Prepare the project to quickly adapt to the official input/output format revealed in the kickoff, without refactoring the core.

## Deliverables

- `router/adapters/official` folder.
- Official adapter interface.
- Templates for text, JSON, JSONL, and file.
- Contract tests.
- Kickoff checklist.

## Checklist

- [x] Create `OfficialAdapter` interface.
- [x] Create `plain_text` adapter.
- [x] Create `json_task` adapter.
- [x] Create `jsonl_batch` adapter.
- [x] Create `file_payload` adapter.
- [x] Create example fixture per format.
- [x] Create round-trip tests.
- [x] Document how to adapt in 30 minutes.
- [x] Create `KICKOFF_CHECKLIST.md`.
- [x] Ensure the core does not know official details.

## Acceptance Criteria

- [x] A new format can be added without modifying the cascade.
- [x] Tests prove input -> `TaskEnvelope` -> final output.
- [x] The kickoff checklist explains exactly where to edit.

## Evidence

- `router/adapters/official/README.md`
- `fixtures/official/`
- `KICKOFF_CHECKLIST.md`
- `tests/test_official_adapters.py`
- `python3 -m unittest discover -s tests`

## Result

Ready adapters:

- `plain_text`
- `json_task`
- `jsonl_batch`
- `file_payload`

The core remains isolated: `router/core` does not import `router.adapters.official`.

## Risks

- Trying to predict the official format too much.
- Coupling the adapter to the evaluator before knowing the real contract.

## Expected Output

A clear integration point for the kickoff, without disrupting the offline path.
