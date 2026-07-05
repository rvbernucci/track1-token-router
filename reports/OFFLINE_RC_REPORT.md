# Offline Release Candidate Report

## Scope

This release candidate covers only work that does not require AMD Developer Cloud or Fireworks credits.

## Completed offline sprints

- Sprint 06: offline evaluation arena.
- Sprint 07: routing policy lab.
- Sprint 08: fake provider chaos lab.
- Sprint 09: official adapter readiness.
- Sprint 10: offline release candidate.

## Verification commands

```bash
scripts/offline_release_check.sh
```

This runs:

- unit tests;
- golden eval;
- offline eval arena;
- routing policy comparison;
- fake provider CLI smoke;
- secret scan.

## Offline dataset

- total tasks: 160
- categories: 8
- tasks per category: 20
- metadata: `category`, `difficulty`, `expected_route`, `risk`

## Policy comparison snapshot

| Policy | Exact match | Escalation rate | Replacement rate | Simulated remote tokens |
|---|---:|---:|---:|---:|
| `aggressive` | `0.75` | `0.375` | `0.0` | `0` |
| `balanced` | `1.0` | `0.5` | `0.125` | `5600` |
| `conservative` | `1.0` | `0.625` | `0.5` | `22400` |

Temporary default: `balanced`.

## No-credit readiness

- The project can run in `mock` mode with no services.
- The fake provider can simulate local and Fireworks endpoints.
- Official adapters can be extended without touching `router/core`.
- Credit activation is isolated in `CREDIT_ACTIVATION.md`.

## Remaining credit-gated work

- AMD runtime bring-up.
- Fireworks real calibration.
- End-to-end cost benchmark.
- Final cloud submission drill.
