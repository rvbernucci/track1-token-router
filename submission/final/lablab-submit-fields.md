# lablab.ai Submission Fields

Use this as the copy-paste source of truth for the final hackathon form.

## Project Title

ProofRoute: Token-Efficient AI Agent

## Short Description

An accuracy-first agent that proves deterministic answers locally and routes unsupported tasks to the best permitted Fireworks model, protecting quality while reducing scored tokens.

## Long Description

ProofRoute is a general-purpose, token-efficient AI agent built for AMD Developer Hackathon ACT II Track 1. It handles factual Q&A, mathematics, sentiment analysis, summarization, named-entity recognition, code debugging, logic puzzles and code generation. The business idea is simple: not every query should pay for the most expensive intelligence.

Each untouched task first reaches a proof-carrying deterministic layer. A zero-Fireworks-token answer is released only when the system can derive a unique, independently recomputable result. Unsupported or uncertain work is routed through the evaluator-provided `FIREWORKS_BASE_URL`, using only models authorized through `ALLOWED_MODELS`. The Answer Contract Engine performs safe mechanical formatting repairs and reconstructs the official `results.json` response.

We also trained FunctionGemma 270M on AMD and evaluated Gemma 4 E2B as a zero-token local responder. Across 2,000 post-contract answers, E2B produced 828 correct responses. An intent-specific matrix regression identified a selective cohort with 84.52% out-of-fold precision and 12.66% coverage. This research is documented reproducibly without pretending the local model is bundled in the zero-download release.

The public Linux `amd64` image is only 45.7 MB compressed and passed the 4 GB RAM, 2 vCPU, no-network, public-pull and official-output gates. It contains no credentials, cached answers or startup downloads.

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

ghcr.io/rvbernucci/track1-token-router:v2.1.0-proof-router

## Release Evidence

- release_tag: `v2.1.0-proof-router`
- commit_sha: `869dbfc8fe31098ca1425f1b02ff3043d1068ca4`
- ci_status: `green`
- release_status: `green`
- image_audit_status: `green`
- image_platform: `linux/amd64`
- image_compressed_size_bytes: `45737139`

## Image Audit Command

```bash
python3 scripts/competition_submission_audit.py \
  --image ghcr.io/rvbernucci/track1-token-router:v2.1.0-proof-router \
  --expected-revision 869dbfc8fe31098ca1425f1b02ff3043d1068ca4 \
  --expected-version v2.1.0-proof-router
```

## Notes

- Submit the Docker image above for Track 1.
- Use the local MP4 if lablab accepts uploads; replace with a hosted URL if the form requires a link.
- Keep this file aligned with `submission/final/submission-status.json`.
