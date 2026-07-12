# Sprints 71-75 - Final Seven-Hour Plan

## Critical Path

| Sprint | Focus | Timebox | Promotion output |
|---|---|---:|---|
| [71](71-semantic-router-q8-promotion/README.md) | FunctionGemma semantic-v3 Q8 parity | 45 min | Hash-pinned Q8 champion |
| [72](72-cluster-augmented-e2b-regression/README.md) | Cluster-augmented per-intent regression | 60 min | Runtime-small candidate policy |
| [73](73-wilson-nash-risk-ladder/README.md) | Wilson 90 risk and minimax routing ladder | 60 min | Deterministic four-tier selector |
| [74](74-fireworks-verify-repair-ood-arena/README.md) | One-call review economics and fresh OOD audit | 75 min | Evidence-backed review strata |
| [75](75-final-nine-hour-release-lock/README.md) | Exact image, public release and submission lock | 150 min | Audited championship image |

Execution time: `390 minutes`. Protected submission and rollback reserve: `30 minutes`. Total: `420 minutes`.

## Seven-Hour Schedule

- `T+00-T+45`: finish Sprint 71 while preparing Sprint 72 matrices locally.
- `T+45-T+105`: freeze the Sprint 72 feature contract and candidate artifact.
- `T+105-T+165`: implement and replay the Sprint 73 Wilson-Nash ladder.
- `T+165-T+240`: run the compact Sprint 74 paired arena and freeze eligible strata.
- `T+240-T+390`: integrate, test, build, pull and audit the Sprint 75 image.
- `T+390-T+420`: update the submission or roll back; no code or policy changes.

## Parallel Execution

- Sprint 71 Q8 evaluation runs on the AMD pod while Sprint 72 analysis runs locally.
- Sprint 73 policy and tests can begin after Sprint 72 freezes its feature contract.
- Sprint 74 OOD generation can run while Sprint 73 replay executes.
- Sprint 75 documentation can begin before the image build, but measured claims remain placeholders until gates finish.

## Stop Rules

- Accuracy regressions override token savings.
- Invalid local assessments or contracts route to Fireworks.
- Failed cluster cohorts remain experimental.
- Review strata without positive token break-even use direct Fireworks.
- If the new image misses any official gate, submit the already audited Sprint 70 image.
- Preserve the final `30-minute` submission and rollback reserve without exception.
- Stop Sprint 74 early if image integration has not started by `T+240`.
