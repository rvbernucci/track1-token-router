# Sprint 64 - Final Hybrid Promotion And Submission Lock

## Objective

Convert validated evidence into one immutable public image, one submission reference and one rollback decision before the extended deadline.

## Promotion Review

- [x] Verify Sprint 60 exact-image local inference evidence.
- [x] Verify Sprint 61 three-route and failure-injection evidence.
- [x] Verify Sprint 62 memory, latency and ten-minute batch evidence.
- [x] Verify Sprint 63 accuracy, token and spend evidence.
- [x] Record accepted risks and residual testing gaps.
- [x] Select full hybrid without mixing its claims with the compact rollback.

## Release

- [x] Freeze configuration hashes, model hashes and E2B threshold `0.75`.
- [x] Run 605 unit/integration tests, contracts, secret and reproducibility checks.
- [x] Build and push final `linux/amd64` tag `v3.3.0-full-hybrid`.
- [x] Remove local image state and pull the public image.
- [x] Re-run 4 GB, 2 vCPU, no-network and 600-second gates on the published digest.
- [x] Verify compressed image size is `2,666,216,379` bytes, below 10 GB.
- [x] Record OCI manifest, platform digest, revision and source labels.

## Submission Lock

- [ ] Update the lablab.ai Docker field to the promoted immutable tag (external manual action).
- [x] Update repository README and submission notes with final measured claims.
- [x] Confirm the GitHub repository and GHCR image are public through release audit.
- [x] Preserve the previous known-good image as documented rollback.
- [ ] Capture a screenshot or export of the final submitted form.
- [x] Freeze experimental architecture changes after the final tag.

## Gates

- [x] Public image passes a clean public pull.
- [x] Public image digest matches the audited digest.
- [x] Repository submission claims match measured evidence exactly.
- [x] Secret scan reports zero credentials.
- [x] CI, release and exact-image audit are green.
- [x] Rollback can be completed by changing one Docker tag in the form.

## Evidence

- `submission/final/final-release-decision.json`
- `submission/final/final-image-audit.json`
- `submission/final/submission-lock-checklist.md`
- `reports/public/final-hybrid-scorecard.md`

## Command

```bash
python3 scripts/final_submission_lock.py \
  --candidate ghcr.io/rvbernucci/track1-token-router:v3.3.0-full-hybrid \
  --rollback ghcr.io/rvbernucci/track1-token-router:v2.1.0-proof-router \
  --revision cfeacd407ac7488883afdc6df580fb86b48a039e \
  --manifest-digest sha256:6bcff04a9b5929b3788345d41304e3d6b98a9901116546afb16ae1e9445139ed \
  --platform-digest sha256:60677fbae98c2043f4c708de8cac00967cdcf5c41a0ef18f24cf0c116de9f2a0 \
  --compressed-size-bytes 2666216379 \
  --release-run 29158458646 --local-gate-run 29158947843 \
  --strict --json
```

## Completion Decision

Promote full hybrid. All technical hard gates are green. The only remaining actions are updating the authenticated lablab.ai Docker field and capturing the final form; use `v2.1.0-proof-router` for a one-field rollback.
