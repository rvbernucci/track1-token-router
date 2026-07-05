# Kickoff Checklist

Use this when the official Track 1 task format is revealed.

## First 15 minutes

- Identify official input format: text, JSON, JSONL, file payload, or another envelope.
- Identify official output format: raw answer, JSON object, JSONL, file, or status wrapper.
- Identify scoring command and timeout.
- Identify whether batch execution is required.
- Identify whether stdout must be answer-only.

## Adapter decision

- If raw text: start from `PlainTextAdapter`.
- If one JSON object: start from `JsonTaskAdapter`.
- If JSONL batch: start from `JsonlBatchAdapter`.
- If files are included: start from `FilePayloadAdapter`.
- If different: create a new adapter in `router/adapters/official`.

## Edit points

- Adapter code: `router/adapters/official/`.
- Fixtures: `fixtures/official/`.
- Tests: `tests/test_official_adapters.py`.
- CLI integration if needed: `router/cli/main.py`.

## Do not touch unless necessary

- `router/core/contracts.py`
- `router/core/local_cascade.py`
- `router/core/hybrid_cascade.py`
- `router/core/prompts.py`

The core should stay stable. The adapter absorbs official format changes.

## Final sanity check

- Run adapter round-trip tests.
- Run `scripts/verify.sh`.
- Confirm `stdout` behavior.
- Confirm logs do not include secrets.
- Commit the adapter change separately.
