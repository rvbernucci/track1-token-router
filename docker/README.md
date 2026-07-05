# Docker

Containerizacao do runner.

## Build

```bash
docker build -t track1-token-router .
```

## Smoke tests

```bash
docker run --rm track1-token-router --help
docker run --rm track1-token-router ask "What is 2+2?"
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
