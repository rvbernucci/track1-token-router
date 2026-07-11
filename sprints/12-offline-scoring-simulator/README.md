# Sprint 12 - Offline Scoring Simulator

## Type

Does not depend on credit.

## Objective

Create an offline scoring simulator that combines simulated quality, remote tokens, latency, and parsing failures to compare policies as if they were competitors.

## Deliverables

- Offline scoring module.
- `scripts/offline_score_simulator.py` script.
- Configurable weights via CLI.
- Markdown and JSON leaderboard.
- Tests covering score calculation and ordering.
- Integration into the offline release check.

## Checklist

- [x] Create `router/evals/scoring.py`.
- [x] Define offline score formula.
- [x] Include simulated accuracy.
- [x] Penalize simulated remote tokens.
- [x] Penalize simulated latency.
- [x] Penalize parse failures.
- [x] Create `scripts/offline_score_simulator.py` script.
- [x] Generate `reports/generated/offline-scoreboard.md`.
- [x] Generate `reports/generated/offline-scoreboard.json`.
- [x] Add score tests.
- [x] Document weights and interpretation.
- [x] Integrate into `scripts/offline_release_check.sh`.

## Acceptance Criteria

- The simulator runs without AMD and without Fireworks.
- The leaderboard compares `aggressive`, `balanced`, and `conservative`.
- The formula is explicit and tested.
- The offline release check continues to pass.

## Expected Output

An offline scoreboard that helps choose a policy before having real credits.

## Local evidence

```bash
python3 scripts/offline_score_simulator.py
python3 -m unittest tests.test_offline_scoring
scripts/offline_release_check.sh
```

## Formula

```text
score = exact_match_rate * accuracy_weight
  - remote_tokens_total * remote_token_weight
  - latency_ms_total * latency_ms_weight
  - parse_failures * parse_failure_weight
```

Default weights:

- `accuracy_weight=1000.0`
- `remote_token_weight=0.02`
- `latency_ms_weight=0.001`
- `parse_failure_weight=25.0`
