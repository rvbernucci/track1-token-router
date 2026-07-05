# Testing Culture

This project uses three testing layers.

## 1. Playground

Use `playground/` for quick manual experiments, similar to a TypeScript `test.ts`.

Good uses:

- inspect a prompt packet;
- test one adapter with a fixture;
- compare route decisions;
- reproduce an idea before turning it into a real test.

Run examples:

```bash
python3 playground/test_policy_logic.py
python3 playground/test_adapter_logic.py
python3 playground/test_prompt_packets.py
```

Playground files must not require real AMD or Fireworks credits.

## 2. Automated Tests

Use `tests/` for guarantees that should run in CI.

Promote playground logic into `tests/` when it:

- catches a real bug;
- protects input/output contracts;
- affects scoring, routing, token usage, or fallback behavior;
- has been used more than once;
- documents an important edge case.

Run all tests:

```bash
python3 -m unittest discover -s tests
```

## 3. Fixtures

Use `fixtures/` for stable examples shared by adapters, tests, and docs.

Fixtures should be:

- small;
- deterministic;
- secret-free;
- easy to inspect in code review.

## Required Checks For New Logic

Before merging new logic, ask:

- Does this change touch scoring, tokens, route decisions, prompts, adapters, or provider behavior?
- If yes, is there an automated test?
- If not, is there at least a playground file documenting the experiment?
- Is there a fixture if the behavior depends on an input format?
- Does `scripts/offline_release_check.sh` still pass?

## Anti-Patterns

- Manual-only logic that affects scoring.
- Tests that depend on real API credits.
- Prompt tests that assert full prompt text when only contract shape matters.
- Debug output mixed into `stdout`.
- Large fixtures that hide the actual edge case.
