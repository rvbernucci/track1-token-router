# Sprint 05 - Hardening and delivery

## Objective

Transform the competitive prototype into a reliable submission: container, documentation, final tests, reproduction scripts, and demo plan.

This sprint is about not losing due to an operational detail.

## Deliverables

- Final Dockerfile.
- Documented build and run commands.
- `.env.example`.
- Public submission README.
- Final test suite.
- Strategy report.
- lablab delivery checklist.

## Checklist

- [x] Create minimalist Dockerfile.
- [x] Create `.dockerignore`.
- [x] Create `.env.example` without secrets.
- [x] Ensure `router --help` works in the container.
- [x] Ensure `router ask` works in the container.
- [x] Ensure `router run --jsonl` works in the container.
- [x] Ensure no-Fireworks mode for smoke testing.
- [x] Ensure Fireworks mode for actual run.
- [x] Run final eval with golden set.
- [x] Run timeout tests.
- [x] Run invalid JSON tests.
- [x] Run missing file tests.
- [x] Clean logs of secrets or sensitive data.
- [x] Write installation README.
- [x] Write architecture README.
- [x] Write tradeoffs and limitations.
- [x] Prepare a short technical pitch.

## Acceptance Criteria

- [x] Anyone can run the project following the README.
- [x] The container does not depend on hidden local files.
- [x] External failures produce a controlled error.
- [x] Logs are useful but do not leak API keys.
- [x] The project clearly explains why it saves tokens.
- [x] The project is ready for a public repo.

## Evidence

- `python3 -m unittest discover -s tests`
- `scripts/verify.sh`
- `docker build -t track1-token-router .`
- `docker run --rm track1-token-router --help`
- `docker run --rm track1-token-router ask "What is 2+2?"`
- `docker run --rm track1-token-router run --jsonl evals/golden/tasks.jsonl --out /tmp/router-output.jsonl`
- `.github/workflows/ci.yml` validates tests and Docker in GitHub Actions.
- `.env.example`
- `SUBMISSION.md`

Note: The local machine used in this implementation does not have `docker`/`podman` installed. The container gates were coded in the CI for validation in a Docker-enabled environment.

## Public README must contain

- Track 1 problem.
- Core cascade concept.
- How to run locally.
- How to run with Docker.
- Environment variables.
- CLI examples.
- Project structure.
- Token efficiency strategy.
- Known limits.
- How to reproduce local evaluation.

## Risks

- Working locally and failing in the standardized environment.
- Nice README, but broken commands.
- Too heavy container.
- Accidental API key exposure.
- Last-minute refactoring instead of stabilization.

## Freeze Plan

- Freeze contracts before delivery.
- Freeze prompts that had the best Pareto.
- Accept small improvements only if there is a test.
- Avoid new dependencies at the final stage.
- Prioritize reproducibility over elegance.

## Expected Sprint Output

A clean, reproducible, and defensible submission: aligned code, container, README, metrics, and technical narrative.
