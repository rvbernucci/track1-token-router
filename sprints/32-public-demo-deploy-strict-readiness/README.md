# Sprint 32 - Public Demo Deploy And Strict Readiness

## Type

Does not depend on credits.

## Objective

Publish the static demo to a real URL, close the public submission fields that do not depend on AMD/Fireworks, and turn the `--strict` mode into a reliable pre-submission gate.

## Why It Matters

The project already has `demo-site/`, public reports, green CI, and final artifacts. Still, the lablab submission asks for an experience accessible by URL. Without a tested public URL, the demo remains too local for judges and mentors.

## Thesis

The competitive runner remains CLI-first. The public demo is just the layer of explanation, reproduction, and evidence.

## Deliverables

- Workflow or runbook of GitHub Pages to publish `demo-site/`.
- `docs/DEMO_DEPLOYMENT.md`.
- Update of `submission/final/submission-status.json`.
- Update of `submission/final-checklist.md`.
- Test/check that validates internal links of the demo.
- `scripts/check_demo_site.py`.
- Report `reports/generated/demo-site-check.md`.

## Checklist

- [x] Decide deployment path: GitHub Pages via Actions or manual Pages.
- [x] Create `docs/DEMO_DEPLOYMENT.md`.
- [x] Create `scripts/check_demo_site.py`.
- [x] Validate that `demo-site/index.html` references only publishable assets.
- [x] Validate links to `public-reports/*.md`.
- [x] Validate links to README and SUBMISSION on GitHub.
- [x] Validate absence of secrets, private IPs, and local paths in the demo.
- [x] Publish HTTPS URL of the demo.
- [x] Update `submission/final/submission-status.json` with `demo_url`.
- [x] Update `ci_status` automatically or by documented command.
- [x] Make `python3 scripts/submission_readiness_check.py --strict` fail only for real video, if the placeholder remains approved.
- [x] Integrate demo check into `offline_release_check.sh` without depending on the external URL.

## Acceptance Criteria

- There is an HTTPS URL for the demo.
- The demo opens without backend, login, or credits.
- Internal links and public reports pass local check.
- Strict readiness no longer fails for `demo_url`.
- Deployment does not become a dependency of the technical evaluator.

## Metrics

- Valid internal links.
- Total publishable size of `demo-site/`.
- Number of sanitization issues.
- Strict status before/after.

## Expected Commands

```bash
python3 scripts/check_demo_site.py --check --report reports/generated/demo-site-check.md
python3 scripts/submission_readiness_check.py --strict
```

## Risks

- Publishing the demo with broken links.
- Confusing visual demo with competitive runtime.
- Marking `ci_status=green` manually and forgetting to validate the current commit.

## Decision

The deploy must be static, cheap, and reversible. If it requires backend, auth, database, or secrets, it is out of scope.

## Definition of Done

- Demo published to HTTPS URL.
- Strict readiness updated.
- Local demo check exists.
- Final checklist reflects real submission state.
