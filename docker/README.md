# Docker

Containerizacao do runner.

## Build

```bash
docker build -t track1-token-router .
```

Official judging runs on `linux/amd64`. If building on Apple Silicon, use:

```bash
docker buildx build --platform linux/amd64 -t track1-token-router .
```

## Public GHCR image

Release tags publish a `linux/amd64` image to GHCR:

```text
ghcr.io/rvbernucci/track1-token-router:<tag>
```

For an offline release candidate:

```bash
git tag offline-rc-YYYYMMDD-HHMM
git push origin offline-rc-YYYYMMDD-HHMM
docker pull ghcr.io/rvbernucci/track1-token-router:offline-rc-YYYYMMDD-HHMM
```

If Docker is not available locally, verify the registry artifact directly:

```bash
python3 scripts/competition_submission_audit.py \
  --image ghcr.io/rvbernucci/track1-token-router:offline-rc-YYYYMMDD-HHMM
```

For final traceability, include the release commit and tag:

```bash
python3 scripts/competition_submission_audit.py \
  --image ghcr.io/rvbernucci/track1-token-router:offline-rc-YYYYMMDD-HHMM \
  --expected-revision "$(git rev-list -n 1 offline-rc-YYYYMMDD-HHMM)" \
  --expected-version offline-rc-YYYYMMDD-HHMM
```

The audit checks public pullability, `linux/amd64`, the 10GB image limit, and OCI source/revision/version labels.

## Smoke tests

```bash
docker run --rm track1-token-router --help
docker run --rm -e ROUTER_MODE=mock track1-token-router ask "What is 2+2?"
```

## Official Track 1 contract

The default container command reads `/input/tasks.json` and writes `/output/results.json`.
The image runs as root by default so it can write to host-owned `/output` mounts in CI and scoring harnesses.

```bash
mkdir -p /tmp/track1-input /tmp/track1-output
cp fixtures/official/lablab_track1_tasks.json /tmp/track1-input/tasks.json
docker run --rm \
  -e ROUTER_MODE=mock \
  -v /tmp/track1-input:/input:ro \
  -v /tmp/track1-output:/output \
  track1-token-router
cat /tmp/track1-output/results.json
```

The Docker default remains `ROUTER_MODE=fireworks` because it is the safest path when no local model endpoint is available. For the championship local-first path, run with `ROUTER_MODE=hybrid` and provide a local OpenAI-compatible endpoint:

```bash
docker run --rm \
  -e ROUTER_MODE=hybrid \
  -e LOCAL_BASE_URL=http://host.docker.internal:8000/v1 \
  -e LOCAL_MODEL=local-model \
  -e FIREWORKS_API_KEY="$FIREWORKS_API_KEY" \
  -e ALLOWED_MODELS="minimax-m3,kimi-k2p7-code,gemma-4-31b-it,gemma-4-26b-a4b-it,gemma-4-31b-it-nvfp4" \
  -v /tmp/track1-input:/input:ro \
  -v /tmp/track1-output:/output \
  track1-token-router
```

## Eval

```bash
docker run --rm \
  -v "$PWD/reports/generated:/app/reports/generated" \
  track1-token-router eval \
  --jsonl evals/golden/tasks.jsonl \
  --expected evals/golden/expected.jsonl \
  --out reports/generated/golden-output.jsonl \
  --report reports/generated/golden-report.md
```

## Hybrid mode

```bash
docker run --rm \
  -e ROUTER_MODE=hybrid \
  -e LOCAL_BASE_URL=http://host.docker.internal:8000/v1 \
  -e LOCAL_MODEL=local-model \
  -e FIREWORKS_API_KEY="$FIREWORKS_API_KEY" \
  -e FIREWORKS_MODEL=accounts/fireworks/models/replace-me \
  track1-token-router ask "What is 2+2?"
```

## Env vars

Use `.env.example` as the safe template. Never commit a real `.env`.
