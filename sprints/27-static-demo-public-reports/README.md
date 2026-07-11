# Sprint 27 - Static Demo And Public Reports

## Type

Does not depend on credits.

## Objective

Create a publishable static demo and a public report export workflow to explain the project quickly without depending on AMD Developer Cloud, Fireworks, Native.Builder, or our own server.

## Why it matters

Lablab documentation requires a prototype accessible via URL. Even though the core is CLI-first, the submission needs to be understood by judges, mentors, and human evaluators in a few minutes.

The objective is not to build a complex UI, but to create a static, secure showroom that is faithful to the competitive runner.

## Thesis

The demo site must answer four questions:

- what the router does;
- why this saves remote tokens;
- how to reproduce locally;
- what offline evidence proves readiness.

## Deliverables

- `demo-site/`.
- `demo-site/index.html`.
- `demo-site/assets/` when necessary.
- `scripts/export_public_report.py`.
- `reports/public/`.
- `reports/public/battle-report.md`.
- `reports/public/fuzz-report.md`.
- `reports/public/submission-readiness.md`.
- `docs/PUBLIC_DEMO_RUNBOOK.md`.
- Update in `submission/demo-plan.md`.
- Tests for export without secrets.

## Checklist

- [x] Create `demo-site/` structure.
- [x] Create static HTML without build tool dependencies.
- [x] Include 90-second pitch.
- [x] Include diagram of the competitive flow.
- [x] Include `solver_arithmetic` example with zero remote tokens.
- [x] Include remote audit dry-run example.
- [x] Include links to README, SUBMISSION, and public reports.
- [x] Create `scripts/export_public_report.py`.
- [x] Export public battle report.
- [x] Export public fuzz report.
- [x] Export public submission readiness.
- [x] Redact long prompts before publishing.
- [x] Mask absolute local paths.
- [x] Block private IPs, private hostnames, and tokens.
- [x] Create test that injects a synthetic secret and expects blockage.
- [x] Create local command to serve demo with `python3 -m http.server`.
- [x] Create GitHub Pages checklist.
- [x] Integrate public export into the release check or a dedicated check.

## Acceptance criteria

- `demo-site/index.html` opens locally without installing dependencies.
- `python3 scripts/export_public_report.py --check` passes without secrets.
- `reports/public/` contains only safe artifacts to share.
- The demo site explains the architecture without requiring code reading.
- The demo does not become a dependency of the technical evaluator.

## Metrics

- Time to understand the thesis: target less than 90 seconds.
- Number of public reports exported: minimum 3.
- Secret scan in public reports: zero findings.
- Local reproduction command visible on first scroll.

## Expected commands

```bash
python3 scripts/export_public_report.py --check
cd demo-site
python3 -m http.server 8080
```

## Risks

- Creating a beautiful landing page that is disconnected from the actual runner.
- Publishing logs or prompts that should not leave the repo.
- Spending too much time on visuals before finalizing technical content.

## Decision

The demo must be static, small, and auditable. If an improvement requires a backend, auth, database, or complex deployment, it is out of scope for this sprint.

## Definition of Done

- Static demo exists.
- Public reports are exported by script.
- Secret scan covers shareable artifacts.
- Submission demo checklist points to the new flow.
- Documentation explains how to publish on GitHub Pages or equivalent.

## Evidence

- `demo-site/index.html` created as a static page without build.
- `docs/PUBLIC_DEMO_RUNBOOK.md` created with local flow, 90-second script, and GitHub Pages checklist.
- `scripts/export_public_report.py --check` exports sanitized reports to `reports/public/` and `demo-site/public-reports/`.
- `tests/test_public_reports.py` covers actual export, redaction of paths/IPs, synthetic secret blocking, and demo links.
- `scripts/offline_release_check.sh` executes the public export before the secret scan.
