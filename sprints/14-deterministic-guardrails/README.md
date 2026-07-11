# Sprint 14 - Deterministic Guardrails

## Type

Does not depend on credits.

## Objective

Add an optional deterministic layer before the cascade to resolve or block obvious cases without calling local or remote LLMs.

## Deliverables

- Module `router/core/guardrails.py`.
- Safe deterministic rules.
- Runner wrapper with guardrails.
- Config `ENABLE_GUARDRAILS`.
- Tests for each rule.
- Logs indicating deterministic routing.

## Checklist

- [x] Detect empty input.
- [x] Detect simple greetings.
- [x] Detect simple, safe addition/subtraction calculations.
- [x] Detect literal echo requests.
- [x] Do not solve complex mathematics.
- [x] Create `GuardedRunner`.
- [x] Add config `ENABLE_GUARDRAILS`.
- [x] Integrate without breaking existing modes.
- [x] Add tests.
- [x] Document limitations.

## Acceptance criteria

- Guardrails can be turned on/off via environment variables.
- Deterministic cases resolve without model calls.
- Complex cases fall back to the normal runner.
- Tests prove that the layer is conservative.

## Expected output

Local/remote savings on trivial tasks, without turning regex into a reasoning engine.

## Local evidence

```bash
python3 -m unittest tests.test_guardrails
ENABLE_GUARDRAILS=1 python3 -m router ask "What is 12 - 5? Return only the number." --json
scripts/offline_release_check.sh
```

## Limitations

- Does not solve multiplication, division, percentage, algebra, dates, or word problems.
- Does not attempt to judge broad difficulty.
- In the current architecture, `sub_intent`, `deterministic_fit`, and regression make the solver a candidate; it must still accept the original input.
