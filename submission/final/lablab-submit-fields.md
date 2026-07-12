# lablab.ai Submission Fields

Use this as the copy-paste source of truth for the final hackathon form.

## Project Title

Track 1 Token Router

## Short Description

Accuracy-first hybrid router combining proof solvers, calibrated local Gemma inference, Wilson-Nash risk control and authorized Fireworks fallback.

## Long Description

ProofRoute is a CLI-first hybrid agent for AMD Developer Hackathon Track 1. The engine removes the official JSON envelope before inference and reconstructs `/output/results.json` deterministically afterward. Each untouched prompt first reaches fail-closed proof solvers. Remaining tasks are assessed by embedded, fine-tuned FunctionGemma 270M Q8. Its intent and five scores feed a per-intent matrix that may select embedded, text-only Gemma 4 E2B. A hash-pinned Wilson 90% and Nash/minimax guard can reject, but never expand, that calibrated local cohort. Every refusal, uncertainty or local failure falls through to a model authorized at runtime by `ALLOWED_MODELS`, exclusively through `FIREWORKS_BASE_URL`.

The Answer Contract Engine performs only unambiguous mechanical normalization and leaves final JSON construction to code. This prompt-envelope boundary reduced Fireworks input tokens by 51.9% in controlled ablation while preserving byte-identical Kimi answers. The championship image embeds both local models, performs no startup downloads and passed 682 tests plus public `linux/amd64`, 4 GB RAM, 2 vCPU, no-network, exact local-inference and hostile harness gates. The exact image produced two E2B answers with zero Fireworks tokens, a 9.737-second cold start and 745.7 MiB sampled peak memory.

## Tags

- AMD Developer Cloud
- DigitalOcean MI300X
- Fireworks AI
- Gemma
- Token Efficiency
- Routing Agent
- Model Evaluation
- Holdout Testing
- Game Theory
- CLI Runner
- Python
- Hackathon Track 1

## Track

Track 1 - Hybrid Token-Efficient Routing Agent

## Public Repository

https://github.com/rvbernucci/track1-token-router

## Demo URL

https://rvbernucci.github.io/track1-token-router/

## Video URL

Local MP4 included in repository: submission/final/proofroute-retro-cli.mp4

## Public Docker Image

ghcr.io/rvbernucci/track1-token-router:v3.7.1-harness-safe

## Release Evidence

- release_tag: `v3.7.1-harness-safe`
- commit_sha: `9f5aef59097c56531ce553a2f87f9b9eb26ab197`
- ci_status: `green`
- release_status: `green`
- image_audit_status: `green`
- image_platform: `linux/amd64`
- image_compressed_size_bytes: `2666354372`

## Image Audit Command

```bash
python3 scripts/competition_submission_audit.py \
  --image ghcr.io/rvbernucci/track1-token-router:v3.7.1-harness-safe \
  --expected-revision 9f5aef59097c56531ce553a2f87f9b9eb26ab197 \
  --expected-version v3.7.1-harness-safe
```

## Notes

- Submit the Docker image above for Track 1.
- Use the local MP4 if lablab accepts uploads; replace with a hosted URL if the form requires a link.
- Keep this file aligned with `submission/final/submission-status.json`.
