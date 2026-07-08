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

## Smoke tests

```bash
docker run --rm track1-token-router --help
docker run --rm -e ROUTER_MODE=mock track1-token-router ask "What is 2+2?"
```

## Official Track 1 contract

The default container command reads `/input/tasks.json` and writes `/output/results.json`.

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
