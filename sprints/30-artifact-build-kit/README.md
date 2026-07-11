# Sprint 30 - Artifact Build Kit

## Type

Does not depend on credit.

## Objective

Transform submission texts into final or semi-final artifacts: PDF slides, PNG/JPG cover, recording script, video checklist, and strict readiness mode.

## Why it matters

Lablab also evaluates presentation. A technically strong project can lose clarity if the video, slide deck, cover, and demo URL are improvised at the last minute.

## Thesis

Final artifacts must be buildable as code. Anything that can be validated by a script should not rely on human memory on submission day.

## Deliverables

- `submission/final/`.
- `submission/final/slides.pdf` or a documented pipeline to generate it.
- `submission/final/cover.png` or `cover.jpg`.
- `submission/recording-shotlist.md`.
- `submission/final-checklist.md`.
- `scripts/build_submission_artifacts.py`.
- `scripts/submission_readiness_check.py --strict`.
- Tests for strict mode.

## Checklist

- [x] Create video shotlist per scene.
- [x] Create exact commands that appear in the video.
- [x] Create short speaker notes per slide.
- [x] Generate or prepare `slides.pdf`.
- [x] Generate or prepare PNG/JPG cover.
- [x] Create checklist for audio, screen, terminal, and timing.
- [x] Create `submission/final/` folder.
- [x] Create artifact build/validation script.
- [x] Add `--strict` to the readiness check.
- [x] In `--strict`, require repo URL.
- [x] In `--strict`, require demo URL.
- [x] In `--strict`, require MP4 video or approved placeholder.
- [x] In `--strict`, require PDF slides.
- [x] In `--strict`, require PNG/JPG cover.
- [x] In `--strict`, require reported green CI.
- [x] Document pending tasks that are only closed at kickoff.

## Acceptance criteria

- Normal mode still passes without heavy final artifacts.
- Strict mode fails as long as final URLs and files do not exist.
- The team knows exactly what to record in up to 5 minutes.
- Slides and cover follow the Track 1 narrative.

## Metrics

- Estimated video duration.
- Number of slides.
- Final files size.
- Number of remaining pending items in strict mode.

## Expected commands

```bash
python3 scripts/build_submission_artifacts.py --check
python3 scripts/submission_readiness_check.py --strict
```

## Risks

- Spending time on design and forgetting reproducibility.
- Creating large binary files unnecessarily.
- Making promises in the pitch that the runner does not yet fulfill.

## Decision

The artifact kit must be pragmatic. If an artifact cannot yet be finalized without credit, the sprint should leave a validated placeholder and an exact list of what is missing.

## Definition of Done

- Shotlist exists.
- `--strict` mode exists.
- Final artifacts or controlled placeholders exist.
- Final checklist covers lablab, repo, video, slides, cover, demo URL, and CI.

## Evidence

- `submission/recording-shotlist.md` defines video scenes, timing, and commands.
- `submission/final-checklist.md` covers lablab, repo, demo, video, artifacts, and kickoff.
- `scripts/build_submission_artifacts.py --check` generates `submission/final/slides.pdf`, `cover.png`, `speaker-notes.md`, `artifact-manifest.json`, `README.md`, and video placeholder.
- `scripts/submission_readiness_check.py --strict` requires repo URL, demo URL, green CI, PDF slides, PNG/JPG cover, and video or approved placeholder.
- `tests/test_submission_readiness.py` covers builder, pending strict, and approved strict in a temporary fixture.
- Expected current state of strict: fails only due to missing `demo_url` and `ci_status` not yet marked as `green`.
