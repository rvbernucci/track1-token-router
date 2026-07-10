# lablab.ai Submission Fields

Use this as the copy-paste source of truth for the final hackathon form.

## Project Title

Track 1 Token Router

## Short Description

Accuracy-first token router: fail-closed local solvers, validation-selected Kimi, strict outputs, and evidence-backed rejection of unsafe local-model routes.

## Long Description

Track 1 Token Router is a CLI-first competitive agent for AMD Developer Hackathon Track 1. It offers each untouched task to a fail-closed deterministic solver, then calls validation-selected Kimi K2.7 Code only when the model is authorized by the evaluator's `ALLOWED_MODELS`. Dynamic completion ceilings, strict output validation, safe mechanical repairs and ranked fallback protect accuracy while limiting scored Fireworks tokens.

The team also trained FunctionGemma 270M on AMD and tested a quantized, text-only Gemma 4 E2B route on 2,000 tasks. That challenger fit the memory envelope but failed the frozen accuracy gate, so it was excluded from the final image. The same holdout rejected per-intent, matrix and Minimax-only policies. The promoted deterministic-plus-Kimi runtime produced the strongest eligible accuracy with fewer tokens and the smallest operational surface.

The system is headless and evaluator-friendly: stdout stays clean, logs are structured JSONL, adapters isolate official formats, and the final public Linux `amd64` image requires no startup model download.

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

Local MP4 included in repository: submission/final/demo.mp4

## Public Docker Image

ghcr.io/rvbernucci/track1-token-router:offline-rc-20260709-1708

## Release Evidence

- release_tag: `offline-rc-20260709-1708`
- commit_sha: `0b43bbde64237839f9594ef42446aa9325967c40`
- ci_status: `green`
- release_status: `green`
- image_audit_status: `green`
- image_platform: `linux/amd64`
- image_compressed_size_bytes: `45070441`

## Image Audit Command

```bash
python3 scripts/competition_submission_audit.py \
  --image ghcr.io/rvbernucci/track1-token-router:offline-rc-20260709-1708 \
  --expected-revision 0b43bbde64237839f9594ef42446aa9325967c40 \
  --expected-version offline-rc-20260709-1708
```

## Notes

- Submit the Docker image above for Track 1.
- Use the local MP4 if lablab accepts uploads; replace with a hosted URL if the form requires a link.
- Keep this file aligned with `submission/final/submission-status.json`.
