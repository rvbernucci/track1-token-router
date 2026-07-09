# lablab.ai Submission Fields

Use this as the copy-paste source of truth for the final hackathon form.

## Project Title

Track 1 Token Router

## Short Description

Local-first routing agent that preserves answer quality while minimizing remote Fireworks tokens through guardrails, deterministic solvers, local verification, budget policy and compact remote audit.

## Long Description

Track 1 Token Router is a CLI-first competitive agent for the AMD Developer Hackathon Track 1 challenge. The project treats token efficiency as an orchestration problem, not as a single prompt trick. It answers easy mechanical tasks with guardrails and deterministic solvers, sends broader tasks to a local model, verifies local candidates with a second local pass, and escalates only risky cases to Fireworks as a compact approve-or-replace auditor.

The repository is designed to be reproducible before credits arrive. It includes a no-credit competition mode, fuzz tests for official input uncertainty, an offline scoring arena, battle drill reports, runtime profiles for AMD/DigitalOcean MI300X with vLLM or SGLang, Fireworks activation runbooks, Docker support and CI gates. The main goal is to maximize accuracy while spending remote tokens only when the expected quality gain justifies the cost.

The system is intentionally headless and evaluator-friendly: stdout stays clean, logs are structured JSONL, and adapters isolate official input formats from the core runner.

## Tags

- AMD Developer Cloud
- DigitalOcean MI300X
- Fireworks AI
- Gemma
- vLLM
- SGLang
- Token Efficiency
- Routing Agent
- Local-First AI
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
