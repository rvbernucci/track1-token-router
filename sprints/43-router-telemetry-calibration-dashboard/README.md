# Sprint 43 - Router Telemetry Calibration Dashboard

## Type

Does not depend on credits.

## Objective

Expose operational telemetry of Pareto/Game Theory in reports and JSONL for calibration: each decision must reveal estimated cost, correlation, payoff, strategic label, and reason for choice.

## Thesis

Without telemetry, there is no calibration. The router needs to leave compact, secure, and comparable traces between runs.

## Deliverables

- JSONL trace with `game_theory` fields.
- Extension of `router/analytics/traces.py` for Fireworks decisions.
- Report `reports/generated/router-game-theory-dashboard.md`.
- Redaction of sensitive payloads.
- Telemetry schema tests.

## Checklist

- [ ] Define minimal telemetry schema per task.
- [ ] Record `selected_model`, `domain`, `tier`, `nash_product`, `prisoner_payoff`, `game_label`.
- [ ] Record top 3 candidates by score without exposing complete input.
- [ ] Aggregate metrics by domain/tier/model.
- [ ] Aggregate label counts: cooperate, defect, dominated, auxiliary.
- [ ] Generate offline Markdown dashboard.
- [ ] Add test against secret leaking.
- [ ] Add test of compatibility with existing logs.

## Metrics

- selected model distribution;
- average estimated cost;
- average Nash product;
- average prisoner payoff;
- over-escalation count;
- underqualification count;
- auxiliary exclusion count;
- redaction pass/fail.

## Definition Of Done

- Any offline run generates an auditable dashboard.
- The dashboard explains why models were called.
- Logs do not leak secrets or long payloads.
- `scripts/offline_release_check.sh` continues passing.

## Out of Scope

- Do not create web UI.
- Do not log full responses by default.
- Do not add heavy dashboard dependencies.
