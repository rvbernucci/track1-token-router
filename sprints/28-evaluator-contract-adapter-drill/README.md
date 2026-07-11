# Sprint 28 - Evaluator Contract And Adapter Drill

## Type

Does not depend on credit.

## Objective

Create an explicit matrix of hypotheses for the official evaluator and practice rapid adaptation of new input/output formats before kickoff.

## Why It Matters

The biggest technical risk without credit is not the model. It is the contract. If the official evaluator comes with an unexpected envelope, file, different schema, or rigid output, we need to adapt in minutes.

## Thesis

The core must continue to communicate via `TaskEnvelope` and `AnswerResult`. Any official surprise must be isolated in adapters, fixtures and tests.

## Deliverables

- `docs/EVALUATOR_ASSUMPTIONS.md`.
- `docs/KICKOFF_ADAPTER_DRILL.md`.
- `fixtures/adapter-drill/`.
- At least three simulated evaluator formats.
- Experimental adapters in `router/adapters/official/`.
- Round-trip tests for each format.
- `scripts/adapter_drill.py` script.
- `reports/generated/adapter-drill-report.md` report.

## Checklist

- [x] Map input hypotheses: plain text, JSON, JSONL, file, stdin.
- [x] Map output hypotheses: plain text, JSON, JSONL, file.
- [x] Map scoring hypotheses: accuracy, token count, latency, parse failure.
- [x] Map environment hypotheses: container, env vars, network, paths.
- [x] Map probable prohibitions: dirty stdout, local state, secret in log.
- [x] Create list of questions for kickoff.
- [x] Create `scoring_text_batch` fixture.
- [x] Create `scoring_json_envelope` fixture.
- [x] Create `scoring_file_bundle` fixture.
- [x] Create experimental adapters for the three formats.
- [x] Create parse and format tests.
- [x] Create timed drill.
- [x] Measure adaptation time per format.
- [x] Validate that the core does not import official adapters.
- [x] Document kickoff decision plan.

## Acceptance Criteria

- Each hypothesis has impact, mitigation, and local test.
- Each simulated format has a fixture, adapter, and test.
- The drill shows target time under 30 minutes for a simple adapter.
- Adaptation does not alter `router/core/*`.
- `stdout` remains clean in simulated paths.

## Metrics

- Adapter time per format.
- Number of changes outside `router/adapters/official`.
- Round-trip rate of fixtures.
- Number of kickoff questions still open.

## Expected commands

```bash
python3 scripts/adapter_drill.py --report reports/generated/adapter-drill-report.md
python3 -m unittest tests.test_official_adapters
```

## Risks

- Over-optimizing for invented formats.
- Creating adapters that leak official details to the core.
- Forgetting output formatting and only testing input parsing.

## Decision

Adapters are the edge layer. The competitive core should not know whether the input came from text, JSON, JSONL, zip, or an official dashboard.

## Definition of Done

- Evaluator matrix exists.
- Adapter drill exists.
- Three simulated formats are tested.
- Adaptation time was measured.
- Kickoff questions were documented.

## Evidence

- `docs/EVALUATOR_ASSUMPTIONS.md` documents hypotheses, impact, mitigation, tests, and kickoff questions.
- `docs/KICKOFF_ADAPTER_DRILL.md` defines the adaptation procedure in under 30 minutes.
- `fixtures/adapter-drill/` contains `scoring_text_batch`, `scoring_json_envelope`, and `scoring_file_bundle`.
- `router/adapters/official/` contains experimental adapters for the three formats.
- `scripts/adapter_drill.py --check` generates `reports/generated/adapter-drill-report.md`.
- `tests/test_official_adapters.py` covers parse and format of the three formats.
- `scripts/offline_release_check.sh` runs the drill before the battle drill.
