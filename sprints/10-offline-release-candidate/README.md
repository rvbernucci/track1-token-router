# Sprint 10 - Offline Release Candidate

## Type

Does not depend on credits.

## Objective

Create a release candidate that runs completely without credits, but is ready to receive real endpoints as soon as AMD/Fireworks are released.

## Deliverables

- Release candidate tag or branch.
- CI expanded with fake hybrid.
- Consolidated offline report.
- Final README for operation without credits.
- Credit activation plan.

## Checklist

- [x] Run complete suite.
- [x] Run offline eval arena.
- [x] Run policy comparison.
- [x] Run fake provider chaos lab.
- [x] Run Docker in the CI.
- [x] Generate consolidated report.
- [x] Update `SUBMISSION.md`.
- [x] Create `CREDIT_ACTIVATION.md`.
- [x] Create tag `offline-rc`.
- [x] Confirm that no step requires actual secrets.

## Acceptance Criteria

- [x] Anyone can reproduce the release candidate without credits.
- [x] When credits arrive, the work becomes a configuration of env vars and benchmarking, not refactoring.
- [x] Green CI on final commit/tag.

## Evidence

- `scripts/offline_release_check.sh`
- `reports/OFFLINE_RC_REPORT.md`
- `CREDIT_ACTIVATION.md`
- `.github/workflows/ci.yml`
- tag `offline-rc`

## Result

Offline release candidate ready to operate without real credentials and to receive credits later without structural refactoring.

## Risks

- Release candidate diverging from the real environment.
- Lack of real data hiding latency bottlenecks.

## Expected Output

A competitive offline package, ready to plug in credits when they arrive.
