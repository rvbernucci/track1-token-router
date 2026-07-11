# Sprint 44 - Fireworks Minimal Credit Calibration

## Type

Partially depends on Fireworks credit, but has offline preparation.

## Objective

Use as little credit as possible to calibrate the Pareto/Game Theory matrix with real calls: few prompts, low max tokens, selected models, and real token/latency measurement.

## Thesis

Public benchmarks help, but the hackathon scoring depends on the actual behavior on the Fireworks endpoint. We need a small, controlled, and cheap sample to correct estimated price, latency, and output drift.

## Deliverables

- `evals/fireworks-pareto/minimal-credit-sample.jsonl`.
- `scripts/fireworks_minimal_calibration.py` script.
- Mandatory budget guard in dollars and maximum number of calls.
- `reports/generated/fireworks-minimal-calibration.md` report.
- Calibration patch in router profiles, if data justifies it.

## Offline Checklist

- [ ] Select 2 prompts per critical domain.
- [ ] Define short `max_tokens` per task type.
- [ ] Define budget hard cap.
- [ ] Ensure dry-run prints plan without calling the API.
- [ ] Ensure that `.env.fireworks.local` never appears in the log.
- [ ] Test with fake provider.

## Credit Checklist

- [ ] Run smoke test with 1 cheap prompt.
- [ ] Run minimal sample across candidate models.
- [ ] Capture actual prompt/completion tokens.
- [ ] Capture actual latency.
- [ ] Compare expected choice vs. actual result.
- [ ] Update profiles only if there is evidence.
- [ ] Re-run offline replay with the new parameters.

## Metrics

- total calls;
- total estimated cost;
- total real tokens;
- latency p50/p95;
- output token drift;
- failure rate;
- model rejection of request options;
- accuracy proxy/manual pass rate.

## Definition of Done

- Actual calibration costs little and is reproducible.
- Safe dry-run exists.
- Router parameters are updated only based on evidence.
- The report shows what changed and why.

## Out of Scope

- Do not run large benchmarks with limited credit.
- Do not test all models on all prompts.
- Do not increase `max_tokens` without justification.
- Do not use priority/fast without an explicit reason.
