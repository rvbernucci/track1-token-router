# Submission Rehearsal

## Goal

Run the final demo ritual before recording or submitting: demo URL, CLI proof, decision replay, redaction, strict readiness and final checklist.

This runbook is designed to fit inside a 5 minute video.

## Command

```bash
python3 scripts/submission_rehearsal.py --check --report reports/generated/submission-rehearsal.md
```

## Video Flow

1. Open the public demo URL: `https://rvbernucci.github.io/track1-token-router/`.
2. State the thesis: local-first routing protects quality and spends remote tokens only when risk justifies it.
3. Run the deterministic CLI command.
4. Show decision replay for a current-fact question.
5. Show public reports: battle, fuzz, readiness, trace summary.
6. Show redaction report and strict readiness.
7. Close with the no-credit path and the credit-gated activation path.

## Capture Checklist

- Audio input selected.
- Screen resolution readable.
- Terminal font large enough.
- Browser zoom readable.
- No private tabs, terminals or env vars visible.
- Recording under 5 minutes.
- Final video URL or approved placeholder added to lablab.

## Safety Rule

Only public artifacts may be shown:

- `demo-site/`;
- `reports/public/`;
- `reports/generated/*-report.md` after redaction checks;
- `README.md`, `SUBMISSION.md`, `CREDIT_ACTIVATION.md`.

Do not show raw logs, `.env`, provider dashboards, local paths or long raw model candidates.
