# Sprint 64 - Final Hybrid Promotion And Submission Lock

## Objective

Convert validated evidence into one immutable public image, one submission reference and one rollback decision before the extended deadline.

## Promotion Review

- [ ] Verify Sprint 60 exact-image local inference evidence.
- [ ] Verify Sprint 61 three-route and failure-injection evidence.
- [ ] Verify Sprint 62 memory, latency and ten-minute batch evidence.
- [ ] Verify Sprint 63 accuracy, token and spend evidence.
- [ ] Record accepted risks and residual testing gaps.
- [ ] Select full hybrid or compact proof-router without mixing claims between them.

## Release

- [ ] Freeze configuration hashes, model hashes and threshold.
- [ ] Run all unit, integration, contract, secret and reproducibility checks.
- [ ] Build and push one final `linux/amd64` tag.
- [ ] Remove local build state and anonymously pull the public image.
- [ ] Re-run 4 GB, 2 vCPU, no-network and 600-second gates on the published digest.
- [ ] Verify compressed image size is below 10 GB.
- [ ] Record OCI manifest, platform digest, revision and source labels.

## Submission Lock

- [ ] Update the lablab.ai Docker field to the promoted immutable tag.
- [ ] Update README, Additional Information, slide metrics and demo references.
- [ ] Confirm GitHub repository and demo URLs are public.
- [ ] Preserve the previous known-good image as documented rollback.
- [ ] Capture a screenshot or export of the final submitted form.
- [ ] Stop all experimental changes at least two hours before the deadline.

## Gates

- [ ] Public image passes an anonymous pull.
- [ ] Public image digest matches the audited digest.
- [ ] Submission claims match measured evidence exactly.
- [ ] Secret scan reports zero credentials.
- [ ] CI, release and public-image audit are green.
- [ ] Rollback can be completed by changing one Docker tag in the form.

## Evidence

- `submission/final/final-release-decision.json`
- `submission/final/final-image-audit.json`
- `submission/final/submission-lock-checklist.md`
- `reports/public/final-hybrid-scorecard.md`

## Command

```bash
python3 scripts/final_submission_lock.py \
  --candidate ghcr.io/rvbernucci/track1-token-router:v3.0.0-full-local \
  --rollback ghcr.io/rvbernucci/track1-token-router:v2.1.0-proof-router \
  --strict --json
```

## Completion Decision

Promote only when all hard gates are green. Otherwise submit the already-audited compact rollback image and document the local challenger as reproducible research.
