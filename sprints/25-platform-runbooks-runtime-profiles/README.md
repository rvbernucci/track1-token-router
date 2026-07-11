# Sprint 25 - Platform Runbooks & Runtime Profiles

## Type

Does not depend on credit.

## Objective

Transform the official documentation of AMD Developer Cloud, DigitalOcean, Gemma, Fireworks, and Native.Builder into executable runbooks and runtime profiles ready for activation.

## Why it matters

When credits arrive, we cannot spend the first few hours deciding on commands, ports, env vars, and health checks. Everything that can be prepared offline should be ready.

## Deliverables

- `runtime-profiles/`.
- `.env.example` profiles per platform/model.
- AMD/DigitalOcean MI300X runbook.
- FunctionGemma training runbook.
- Gemma E2B text-only runbook.
- Fireworks serverless runbook.
- Native.Builder runbook as an auxiliary demo.
- Offline health check for profiles.
- Cost and VM destruction checklist.

## Checklist

- [x] Large serving profiles have been retired from the active path.
- [x] The generic Gemma profile has been retired; active profiles now separate FunctionGemma, E2B, and `three_route`.
- [x] Create `runtime-profiles/fireworks-serverless.env.example`.
- [x] Create `docs/RUNBOOK_AMD_DIGITALOCEAN.md`.
- [x] Create `docs/RUNBOOK_GEMMA.md`.
- [x] Create `docs/RUNBOOK_FIREWORKS.md`.
- [x] Create `docs/RUNBOOK_NATIVE_BUILDER.md`.
- [x] Document ports, commands, and health checks.
- [x] Document required and optional variables.
- [x] Document scratch disk strategy.
- [x] Document VM destruction rule to stop costs.
- [x] Create `scripts/check_runtime_profiles.py` script.
- [x] Validate that no profile contains real secrets.
- [x] Integrate profile check with the release check.
- [x] Update `CREDIT_ACTIVATION.md`.

## Acceptance criteria

- Each official platform has a clear runbook.
- Each profile can be validated without credentials.
- The team can activate AMD/Fireworks without redesigning the architecture.
- No real secrets appear in docs, envs, or CI.

## Expected output

Credits stop being an operational blocker and become just a swap of env vars.

## Decision

Runbooks must be reproducible commands, not loose notes. The goal is to reduce activation time at kickoff.

## Closing evidence

- `python3 scripts/check_runtime_profiles.py`: valid profiles without real secrets.
- `python3 -m unittest tests.test_runtime_profiles`: CLI validator and synthetic secret detection tested.
- `python3 scripts/secret_scan.py`: global scanner with no findings.
- `scripts/offline_release_check.sh`: profile check integrated into the heavy release check.
