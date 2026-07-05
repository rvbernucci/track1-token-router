# Demo Plan

## CLI demo

1. Install locally:

```bash
python3 -m pip install -e .
```

2. Run no-credit release gate:

```bash
scripts/offline_release_check.sh
```

3. Show deterministic solver path:

```bash
ROUTER_MODE=competition COMPETITION_DRY_RUN=1 \
python3 -m router ask "What is 6 * 7? Return only the number." --json
```

Expected:

- answer `42`;
- route `solver_arithmetic`;
- remote tokens `0`;
- trace includes `deterministic_solver`.

4. Show strict format repair:

```bash
ROUTER_MODE=competition COMPETITION_DRY_RUN=1 \
python3 -m router ask "Return only compact JSON: {\"ok\":true,\"count\":2}." --json
```

Expected:

- compact JSON output;
- final validation present;
- no remote tokens.

5. Show battle drill:

```bash
python3 scripts/battle_drill.py
```

Expected readiness:

- `competition_mode_ready=true`;
- `solver_pack_ready=true`;
- `fuzz_pack_ready=true`.

## Visual demo optional

- Use `demo-site/index.html` as the default public explanation layer.
- Use Native.Builder only as an optional visual companion for architecture and reports.
- Do not use any visual layer as runtime.
- Do not upload secrets, private IPs, raw traces, long prompts or sensitive logs.

## Static public demo

1. Export safe public reports:

```bash
python3 scripts/export_public_report.py --check
```

2. Serve locally:

```bash
cd demo-site
python3 -m http.server 8080
```

3. Show the first-scroll story:

- thesis: accuracy first, remote tokens only when needed;
- architecture: deterministic solver, local candidate, local verifier, compact remote audit;
- proof: public battle, fuzz and submission readiness reports;
- reproduction: `scripts/offline_release_check.sh`.

Expected public links:

- `demo-site/public-reports/battle-report.md`;
- `demo-site/public-reports/fuzz-report.md`;
- `demo-site/public-reports/submission-readiness.md`.

## Demo URL checklist

- Public GitHub repository URL.
- Optional video URL.
- Optional slide/PDF URL.
- Optional GitHub Pages URL pointing at `demo-site/`.
- Optional Native.Builder demo URL.
- No private dashboards or credential-bearing links.

## Repo public checklist

- README explains install, CLI and Docker.
- `SUBMISSION.md` explains pitch and reproduction.
- `CREDIT_ACTIVATION.md` explains paid activation.
- CI is visible and passing.
- `docs/PUBLIC_DEMO_RUNBOOK.md` explains the publication path.
- `reports/public/` contains only sanitized shareable reports.

## Docker/CI checklist

- `Dockerfile` exists.
- `.github/workflows/ci.yml` exists.
- `scripts/offline_release_check.sh` passes.
- `scripts/submission_readiness_check.py` passes.
