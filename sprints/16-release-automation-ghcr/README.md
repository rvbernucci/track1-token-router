# Sprint 16 - Release Automation & GHCR

## Type

Does not depend on credit.

## Objective

Automate release, tags, release notes, and optional image publication to GitHub Container Registry.

## Deliverables

- Release workflow.
- Multi-event Docker build.
- GHCR publication on tag.
- Release notes script.
- Tags documentation.
- Tests/validations that do not require a local secret.

## Checklist

- [x] Create `release.yml` workflow.
- [x] Publish to GHCR only on tags.
- [x] Use `GITHUB_TOKEN`, no manual secret.
- [x] Create `scripts/generate_release_notes.py`.
- [x] Document tag format.
- [x] Add local dry-run for release notes.
- [x] Validate YAML/workflow in a simple static test.
- [x] Update README.
- [x] Run offline release check.

## Acceptance Criteria

- The workflow exists and is safe for a public repo.
- GHCR does not depend on AMD/Fireworks credit.
- Release notes can be generated locally.
- The automation does not publish on normal pushes to `main`.

## Expected Output

A reproducible path to distribute image and release when we want to tag a version.

## Local evidence

```bash
python3 scripts/generate_release_notes.py --tag offline-dry-run
python3 -m unittest tests.test_release_automation
scripts/offline_release_check.sh
```

## Decision

GHCR publication runs only on `v*` and `offline-*` tags. Normal push to `main` continues using only the CI workflow, without publishing the image.
