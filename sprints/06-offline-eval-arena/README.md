# Sprint 06 - Offline Evaluation Arena

## Type

Does not depend on credit.

## Objective

Create an offline evaluation arena strong enough to calibrate the router before having real access to AMD Developer Cloud or Fireworks.

Without credit, the most important asset is the dataset. It tells us where the cascade fails, where it escalates too much, and where it spends simulated remote tokens unnecessarily.

## Deliverables

- Offline dataset with 100-300 tasks.
- Categories: easy, medium, difficult, format, mathematics, instruction, adversarial, unstable knowledge.
- Expected answers when there is an objective response.
- Difficulty and risk metadata.
- Report by category.
- Command for dataset generation/validation.

## Checklist

- [x] Create `evals/offline/tasks.jsonl`.
- [x] Create `evals/offline/expected.jsonl`.
- [x] Add `metadata.category` field.
- [x] Add `metadata.difficulty` field.
- [x] Add `metadata.expected_route` field.
- [x] Create trivial tasks that should resolve locally.
- [x] Create strict format tasks.
- [x] Create multi-step mathematical tasks.
- [x] Create adversarial prompt injection tasks.
- [x] Create potentially outdated knowledge tasks.
- [x] Create report by category.
- [x] Ensure the dataset does not use sensitive data.

## Acceptance Criteria

- [x] `python3 -m router eval --jsonl evals/offline/tasks.jsonl --expected evals/offline/expected.jsonl` runs without real providers.
- [x] The report shows routes, exact match, escalations, and simulated remote tokens.
- [x] The dataset has minimum coverage per category.
- [x] The README explains how to add new tasks.

## Evidence

- `python3 scripts/generate_offline_eval.py`
- `python3 scripts/generate_offline_eval.py --check`
- `wc -l evals/offline/tasks.jsonl evals/offline/expected.jsonl`
- `python3 -m router eval --jsonl evals/offline/tasks.jsonl --expected evals/offline/expected.jsonl --report reports/generated/offline-report.md`
- `python3 -m unittest discover -s tests`

## Result

- 160 offline tasks.
- 8 categories with 20 tasks each.
- Metadata per task: `category`, `difficulty`, `expected_route`, `risk`.
- `router eval` report includes `categories`, `difficulties`, and `expected_route`.

## Risks

- Dataset too artificial.
- Exact match punishing semantically correct responses.
- Measuring only accuracy and forgetting cost/latency.

## Expected Output

An offline arena that allows continued calibration without depending on credits.
