# Sprint 08 - Fake Provider Chaos Lab

## Type

Does not depend on credits.

## Objective

Create configurable local provider and Fireworks simulators to test failures, latency, timeouts, bad responses, invalid JSON, and token usage without spending credits.

## Deliverables

- Executable fake provider outside of tests.
- Behavior profiles: happy path, slow, flaky, invalid JSON, wrong answer, high token usage.
- Resilience tests per profile.
- Robustness report.
- Documentation to run the cascade against fake providers.

## Checklist

- [x] Transform `tests/fake_openai_server.py` into a reusable utility.
- [x] Create CLI `python3 -m router.dev.fake_provider`.
- [x] Support sequential responses.
- [x] Support artificial delay.
- [x] Support configurable HTTP errors.
- [x] Support configurable token usage.
- [x] Create Fireworks approve/replace scenarios.
- [x] Create invalid JSON scenarios.
- [x] Create end-to-end timeout test.
- [x] Create chaos testing documentation.

## Acceptance criteria

- [x] The legacy fake provider remains as reusable infrastructure for `three_route` fault injection.
- [x] The system behaves correctly under timeout, 500 errors, and invalid JSON.
- [x] Logs show failures without leaking secrets.
- [x] CI runs at least one fake hybrid scenario.

## Evidence

- `python3 -m router.dev.fake_provider --help`
- `python3 -m unittest discover -s tests`
- `scripts/verify.sh`
- `tests/test_hybrid_cascade.py`
- `tests/test_fake_provider.py`
- `docs/CHAOS_LAB.md`

## Supported profiles

- `happy`
- `verifier-approve`
- `verifier-escalate`
- `fireworks-approve`
- `fireworks-replace`
- `wrong-answer`
- `--status 500`
- `--delay-s`
- `--invalid-json`
- `--prompt-tokens` and `--completion-tokens`

## Risks

- The simulator becoming more complex than necessary.
- False sense of security from testing only predictable failures.

## Expected output

A testbed that simulates the war before the war.
