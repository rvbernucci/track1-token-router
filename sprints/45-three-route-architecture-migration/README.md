# Sprint 45 - Assessment And Decision Contracts

Status: **Completed and promoted on 2026-07-09**

## Objective

Replace direct model routing with a two-stage contract:

```text
FunctionGemma perception
-> calibrated feature vector
-> mathematical decision engine
```

FunctionGemma describes the task. It never chooses deterministic, E2B or Fireworks.

## TaskAssessment Contract

```json
{
  "intent": "math_reasoning",
  "scores": {
    "deterministic_fit": 9,
    "reasoning_demand": 2,
    "knowledge_uncertainty": 0,
    "generation_demand": 1,
    "format_complexity": 1
  }
}
```

Every score is an integer from 0 to 10. The schema rejects missing, additional, non-integer and out-of-range values.

## Checklist

- [x] Add immutable `TaskAssessment`, `AssessmentScores` and `EngineDecision` contracts.
- [x] Freeze eight runtime `intent` values and a dataset-only versioned `sub_intent` taxonomy.
- [x] Define behavioral anchors for scores `0`, `2`, `5`, `8` and `10`.
- [x] Generate deterministic solver hints from the registered solver manifest.
- [x] Add code-computed structural features: input tokens, requested shape and deadline remaining.
- [x] Define the canonical feature vector and normalization rules.
- [x] Define per-engine observation rows: correctness, latency, tokens, failure and memory.
- [x] Add schema parsing with Fireworks-safe fallback on invalid assessments.
- [x] Add model-independent interfaces for assessment, prediction and engine selection.
- [x] Preserve CLI, adapters, logs and `/output/results.json`.
- [x] Remove direct-route contracts and retired cascade wiring from active factories.

## Deliverables

- assessment JSON schema;
- score-rubric document and examples;
- feature-vector specification;
- engine-outcome dataset schema;
- migration tests and trace schema.

## Gate

All contracts round-trip deterministically, every invalid assessment fails closed, and no active model output directly selects an execution engine.

## Completion Evidence

- executable gate: `python3 -m unittest tests.test_assessment_contracts`;
- focused result: `17/17` tests passed;
- repository result: `327/327` tests passed;
- release verification: `sh scripts/verify.sh` passed;
- schema artifacts: `task-assessment-v1`, `feature-vector-v1`, `engine-outcome-v1`, `routing-trace-v1`;
- official adapter proof: `three_route` produced valid `results.json` and JSONL traces through the fake Fireworks provider;
- independent review: Claude Sonnet 5 found no correctness or model-controlled-routing defect; schema-hardening findings were implemented before promotion;
- legacy decision: M1/M2A/M2B factory modes are disabled by default and require `ENABLE_LEGACY_CASCADE_MODES=1` only for historical regression tests.

## Promotion Decision

Promote the contracts, schemas and Fireworks-safe `three_route` factory to Sprint 46. Do not yet promote FunctionGemma assessment or local E2B execution; both remain unavailable until their own measured gates pass.
