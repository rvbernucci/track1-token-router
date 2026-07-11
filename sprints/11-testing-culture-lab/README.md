# Sprint 11 - Testing Culture Lab

## Type

Does not depend on credit.

## Objective

Create an explicit testing culture so that all important logic has a clear place to be experimented with, validated, and protected against regression.

In TypeScript, we often use a quick `test.ts` to test an idea. In Python, we will separate this into three layers:

- `playground/`: manual and disposable experiments.
- `tests/`: automated guarantees that run in CI.
- `fixtures/`: stable examples used by tests and adapters.

## Deliverables

- Guide `docs/TESTING_CULTURE.md`.
- `playground/` folder with executable examples.
- Coverage matrix by critical area.
- Script to list tests by domain.
- Promotion rule: playground -> automated test.
- Checklists for new logic.
- CI ensuring that the main examples do not rot.

## Checklist

- [x] Create `docs/TESTING_CULTURE.md`.
- [x] Create `playground/README.md`.
- [x] Create `playground/test_policy_logic.py`.
- [x] Create `playground/test_adapter_logic.py`.
- [x] Create `playground/test_prompt_packets.py`.
- [x] Create `docs/TEST_MATRIX.md`.
- [x] Map areas: contracts, adapters, policies, prompts, cascade, fake provider, evals, CLI.
- [x] Create `scripts/list_test_coverage.py`.
- [x] Add test validating the test matrix.
- [x] Document when to use `playground` versus `tests`.
- [x] Add command in README.

## Acceptance Criteria

- [x] There is a fast way to test logic manually, equivalent to the spirit of a `test.ts`.
- [x] Every piece of critical logic has at least one mapped automated test.
- [x] The matrix makes it clear what is covered and what still needs coverage.
- [x] `scripts/offline_release_check.sh` continues to pass.
- [x] No playground depends on real credit.

## Evidence

- `docs/TESTING_CULTURE.md`
- `docs/TEST_MATRIX.md`
- `playground/test_policy_logic.py`
- `playground/test_adapter_logic.py`
- `playground/test_prompt_packets.py`
- `scripts/list_test_coverage.py --check`
- `tests/test_testing_culture.py`
- `scripts/offline_release_check.sh`

## Result

- 8 critical domains mapped: contracts, adapters, policies, prompts, cascade, fake provider, evals, CLI.
- 3 executable playgrounds without credit.
- 50 automated tests passing.
- Offline release check now validates matrix, playgrounds, and secret scan.

## Promotion Rule

A file in `playground/` should become a test in `tests/` when:

- it captures a real bug;
- it validates competitive behavior;
- it protects the input/output contract;
- it involves scoring, token usage, or routing;
- it is used more than once.

## Out of Scope

- Do not pursue 100% numerical coverage without criteria.
- Do not create tests fragily coupled to exact prompt text when the contract does not require it.
- Do not depend on real models.
- Do not turn playground into a mandatory second parallel suite.

## Expected Output

A clear testing culture: experiment quickly, promote what matters, and keep CI protecting the competitive logic.
