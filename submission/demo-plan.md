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

- Use Native.Builder only to show architecture and reports visually.
- Do not use it as runtime.
- Do not upload secrets, private IPs or sensitive logs.

## Demo URL checklist

- Public GitHub repository URL.
- Optional video URL.
- Optional slide/PDF URL.
- Optional Native.Builder demo URL.
- No private dashboards or credential-bearing links.

## Repo public checklist

- README explains install, CLI and Docker.
- `SUBMISSION.md` explains pitch and reproduction.
- `CREDIT_ACTIVATION.md` explains paid activation.
- CI is visible and passing.

## Docker/CI checklist

- `Dockerfile` exists.
- `.github/workflows/ci.yml` exists.
- `scripts/offline_release_check.sh` passes.
- `scripts/submission_readiness_check.py` passes.
