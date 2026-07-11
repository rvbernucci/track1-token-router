# Sprint 36 - Submission Rehearsal And Log Redaction

## Type

Does not depend on credits.

## Objective

Run a complete submission rehearsal and harden the redaction of logs/traces so that no shareable artifact leaks long prompts, local paths, private IPs, hostnames, or tokens.

## Why It Matters

The project already has sanitized public reports, but there are still internal logs and traces with raw candidates. Before recording videos, publishing demos, or sending materials, we need to separate what is internal from what is shareable.

## Thesis

A strong submission is not just code passing. It is a reproducible ritual: demo, commands, video, reports, checklist, CI, and leak-free artifacts.

## Deliverables

- `scripts/redact_logs.py`.
- `reports/public/traces/` or `reports/public/trace-summary.md`.
- `docs/SUBMISSION_REHEARSAL.md`.
- `reports/generated/submission-rehearsal.md`.
- Fillable video checklist.
- Redaction tests for JSONL logs.

## Checklist

- [x] Map sensitive fields in logs and traces.
- [x] Redact long prompts above a configurable limit.
- [x] Redact long candidates above a configurable limit.
- [x] Mask absolute local paths.
- [x] Block private IPs.
- [x] Block private hostnames.
- [x] Block tokens and env assignments.
- [x] Generate public trace summary.
- [x] Create a 5-minute rehearsal script/runbook.
- [x] Run video commands in order.
- [x] Measure estimated video duration.
- [x] Validate audio/screen/terminal as a checklist.
- [x] Update `submission/final-checklist.md`.

## Acceptance Criteria

- Logs publishable pass secret scan and redaction check.
- Submission rehearsal generates a report.
- Video script fits in 5 minutes.
- The team knows exactly what to open, run, and show on the final day.

## Metrics

- Number of redacted fields.
- Public trace size.
- Total rehearsal time.
- Pending checklist items.
- Secret scan findings.

## Expected Commands

```bash
python3 scripts/redact_logs.py --check --report reports/generated/redaction-report.md
python3 scripts/submission_rehearsal.py --check --report reports/generated/submission-rehearsal.md
```

## Risks

- Redacting so much that the report fails to explain the decision.
- Keeping internal logs publishable by accident.
- Doing the video rehearsal too late.

## Decision

The public artifact must explain decisions without exposing sensitive raw data. Internal and public need to be separate paths.

## Definition of Done

- Log redaction exists.
- Submission rehearsal exists.
- Public trace/report is secure.
- Final checklist becomes actionable for recording and submission.
