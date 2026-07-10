# Docker

## Build

```bash
docker buildx build --platform linux/amd64 -t track1-token-router .
```

The final image must be publicly pullable, below 10 GB compressed and include a Linux `amd64` manifest.

## Current Baseline

```bash
docker build -t track1-token-router .
docker run --rm -e ROUTER_MODE=mock track1-token-router ask "What is 2+2?"
```

## Official Contract Smoke

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

## Championship Gate

The promoted image excludes FunctionGemma and E2B because the local route failed its frozen accuracy gate. Test the exact image with:

```bash
docker run --rm \
  --memory=4g \
  --cpus=2 \
  --network=none \
  track1-token-router
```

The automated equivalent is:

```bash
bash scripts/docker_resource_gate.sh track1-token-router
```

Then repeat with network enabled and injected `FIREWORKS_BASE_URL`, `FIREWORKS_API_KEY` and `ALLOWED_MODELS`.

Verify cold start, full-batch runtime, valid results, preferred-model authorization, Fireworks fallback and controlled failure.

## Release Audit

```bash
python3 scripts/competition_submission_audit.py \
  --image ghcr.io/rvbernucci/track1-token-router:TAG
```

Never download models at evaluator startup and never bake credentials into an image layer.
