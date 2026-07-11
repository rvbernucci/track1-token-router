# Sprint 34 - Semantic Validation Harness

## Type

Does not depend on credit.

## Objective

Create an offline semantic validation harness for free-form and partially open-ended responses, without relying on a paid LLM judge.

## Why it matters

Exact match is excellent for regression, but weak for open-ended questions. If the official evaluator yields free-form responses, we need a richer way to measure "acceptable", "partial", "format fail", and "dangerous".

## Thesis

We do not need a perfect judge without credit. We need a deterministic judge that exposes gross errors and risk classes before spending real tokens.

## Deliverables

- `evals/semantic/`.
- `evals/semantic/tasks.jsonl`.
- `evals/semantic/rubrics.jsonl`.
- `router/evals/semantic_judge.py`.
- `scripts/run_semantic_eval.py`.
- `reports/generated/semantic-eval.md`.
- Tests for rubrics, formats, and error classes.

## Checklist

- [x] Define offline rubric schema.
- [x] Create classes: `acceptable`, `partial`, `format_fail`, `unsafe`, `hallucinated`, `too_verbose`.
- [x] Create open-ended tasks with short explanations.
- [x] Create summarization tasks.
- [x] Create decision-making tasks with criteria.
- [x] Create volatile knowledge tasks that must escalate.
- [x] Implement deterministic judge based on keywords, format, and constraints.
- [x] Measure acceptable/partial/fail rate.
- [x] Integrate categories into the report.
- [x] Ensure that runner stdout remains clean.
- [x] Document semantic judge limitations.

## Acceptance criteria

- The semantic eval runs without an external model.
- The report differentiates exact match from semantic acceptability.
- The harness does not replace official scoring, but improves calibration.
- Open-ended errors appear as interpretable classes.

## Metrics

- Semantic acceptable rate.
- Partial rate.
- Format fail rate.
- Unsafe/hallucination flags.
- Average answer length.

## Expected commands

```bash
python3 scripts/run_semantic_eval.py --check --report reports/generated/semantic-eval.md
python3 -m unittest tests.test_semantic_validation
```

## Risks

- Creating false comfort with a weak rubric.
- Performing overly simplistic keyword matching.
- Confusing the offline judge with the official evaluator.

## Decision

The semantic harness is a risk sensor, not a final judge. It should favor explainability and stability.

## Definition of Done

- Semantic dataset exists.
- Versioned rubrics exist.
- Script and tests pass.
- Battle/readiness can consume the semantic signal if the score is useful.
