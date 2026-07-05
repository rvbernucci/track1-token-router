# Demo Deployment

## Decision

The public demo is deployed as a static GitHub Pages site from `demo-site/`.

The evaluator path remains the CLI/container path. Pages is only the human-facing explanation layer for judges, mentors and the lablab submission form.

## Public URL

Expected URL:

```text
https://rvbernucci.github.io/track1-token-router/
```

This URL is recorded in `submission/final/submission-status.json` as `demo_url`.

## Local Validation

Run before publishing:

```bash
python3 scripts/check_demo_site.py --check --report reports/generated/demo-site-check.md
scripts/offline_release_check.sh
```

The demo check validates:

- `demo-site/index.html` exists and is static;
- internal links resolve inside `demo-site/`;
- required public reports exist;
- GitHub README and SUBMISSION links are present;
- no local absolute paths, private IPs, private hostnames or secret-like tokens are present;
- the site does not depend on backend routes, credentials or cloud credits.

## GitHub Pages Workflow

The deploy workflow lives at `.github/workflows/pages.yml`.

It runs on:

- push to `main`;
- manual `workflow_dispatch`.

The workflow:

- checks out the repo;
- sets up Python;
- runs `scripts/check_demo_site.py --check`;
- uploads `demo-site/` as the Pages artifact;
- deploys it with GitHub Pages Actions.

## Enabling Pages

If GitHub Pages is not enabled yet, set the source to GitHub Actions:

```bash
gh api repos/rvbernucci/track1-token-router/pages \
  --method POST \
  --field build_type=workflow
```

If the site already exists, the same endpoint may return an error. In that case inspect it with:

```bash
gh api repos/rvbernucci/track1-token-router/pages
```

## Post-Deploy Checks

After the workflow finishes:

```bash
gh run list --workflow Pages --limit 1
gh api repos/rvbernucci/track1-token-router/pages
```

Then open:

```text
https://rvbernucci.github.io/track1-token-router/
```

Verify these links:

- Battle report;
- Fuzz report;
- Submission readiness;
- GitHub README;
- GitHub SUBMISSION.

## Safety Boundary

Do not add:

- backend calls;
- auth;
- cloud consoles;
- API keys;
- raw logs;
- long prompts;
- local traces;
- provider responses.

The page must remain static, reproducible and safe to publish.
