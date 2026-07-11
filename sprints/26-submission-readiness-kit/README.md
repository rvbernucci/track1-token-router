# Sprint 26 - Submission Readiness Kit

## Type

Does not depend on credits.

## Objective

Prepare the hackathon submission package before credits: descriptions, tags, video script, slide structure, cover, demo URL, file checklist, and automated readiness check.

## Why It Matters

Even a strong runner can lose if the submission is incomplete, confusing, or difficult to reproduce. The lablab platform requires artifacts beyond the code.

## Deliverables

- `submission/`.
- `submission/short-description.md`.
- `submission/long-description.md`.
- `submission/tags.md`.
- `submission/video-script.md`.
- `submission/slides-outline.md`.
- `submission/demo-plan.md`.
- `submission/cover-brief.md`.
- Script `scripts/submission_readiness_check.py`.
- Report `reports/generated/submission-readiness.md`.
- Update of `SUBMISSION.md`.

## Checklist

- [x] Write short description up to 255 characters.
- [x] Write long description with more than 100 words.
- [x] Define final project title.
- [x] Define technology/category tags.
- [x] Create video script up to 5 minutes.
- [x] Create PDF slide structure.
- [x] Create CLI demo plan.
- [x] Create optional visual demo plan.
- [x] Create PNG/JPG cover image brief.
- [x] Create demo URL checklist.
- [x] Create public repo checklist.
- [x] Create Docker/CI checklist.
- [x] Create readiness script.
- [x] Validate mandatory lablab fields.
- [x] Integrate readiness into battle drill or release check.
- [x] Document what remains pending until kickoff.

## Acceptance Criteria

- The submission has all base texts ready.
- The readiness check fails when a mandatory artifact is missing.
- The README clearly points out how to run and evaluate.
- The team can record videos and create slides without reinventing the narrative.

## Expected Output

A submission package almost ready, waiting only for real details from the kickoff and final URLs.

## Decision

The kit must sell the project as a competitive runner, not as a generic platform. The main narrative is accuracy with lower remote tokens through calibrated orchestration.

## Closure Evidence

- `python3 scripts/submission_readiness_check.py`: `ok=true`, short description with 199 characters, long description with 162 words, 12 tags, and 10 slides.
- `python3 -m unittest tests.test_submission_readiness`: positive readiness, CLI and failure due to missing artifact tested.
- `scripts/offline_release_check.sh`: readiness integrated into the strict release gate.
- Pendencies until kickoff documented as warnings: public URL, video/demo URL, and actual AMD/Fireworks benchmark.
