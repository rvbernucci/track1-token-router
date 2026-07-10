# Public Demo Runbook

## Purpose

This demo is the human-facing explanation layer for the Track 1 Token Router. It must help judges understand the system quickly without becoming part of the technical evaluator path.

The authoritative runtime remains the CLI/container path documented in `README.md`, `SUBMISSION.md` and `submission/demo-plan.md`.

## Local Preview

```bash
python3 scripts/export_public_report.py --check
cd demo-site
python3 -m http.server 8080
```

Open `http://localhost:8080`.

## What To Show In 90 Seconds

1. State the thesis: the router protects accuracy while spending remote Fireworks tokens only when risk justifies it.
2. Point to the flow: FunctionGemma assessment, regression/minimax decision, deterministic/E2B/Fireworks execution.
3. Run or show the arithmetic example: `solver_arithmetic` answers `42` with zero remote tokens.
4. Open the public battle, fuzz and submission readiness reports.
5. Close with reproducibility: `scripts/offline_release_check.sh` validates the no-credit path.

## Public Report Export

The exporter copies selected generated reports into `reports/public/` and mirrors them into `demo-site/public-reports/`.

It redacts local absolute paths and private IPs, and it blocks publication when it detects:

- secret-like API tokens;
- secret-like environment assignments;
- private hostnames such as internal, local, lan, corp or private domains.

Run before publishing:

```bash
python3 scripts/export_public_report.py --check
python3 scripts/secret_scan.py
```

## GitHub Pages Checklist

- Keep the repository public only after `scripts/offline_release_check.sh` passes.
- Publish the `demo-site/` folder as the static site root.
- Confirm the three public report links resolve from the deployed page.
- Do not link private dashboards, cloud consoles or credential-bearing URLs.
- Do not upload raw logs, long prompts, local traces or provider responses.
- Keep the CLI/container route as the official evaluator route.

## Safety Boundary

The static demo may explain architecture, evidence and reproduction commands. It must not store secrets, proxy API calls, depend on Fireworks, depend on AMD credits or replace the runner used by the evaluator.
