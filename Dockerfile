FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ROUTER_LOG_PATH=/app/logs/run.jsonl \
    ROUTER_MODE=fireworks \
    FIREWORKS_MATRIX_WEIGHTS=/app/router/data/fireworks_track1_allowed_weights.json \
    FIREWORKS_INTENT_POLICY=/app/configs/fireworks-intent-policy-v1.json \
    FIREWORKS_INTENT_POLICY_SHA256=f10e31382bb39378834b9ec76c1d11b5b9c6e3e17f5d9bc782909004c8344c91 \
    FIREWORKS_TIMEOUT_S=15 \
    FIREWORKS_MAX_RETRIES=0 \
    ENABLE_GUARDRAILS=1 \
    ENABLE_ORCHESTRATOR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY router ./router
COPY configs ./configs
COPY logs ./logs

RUN pip install --no-cache-dir . && rm -rf /app/build /app/*.egg-info

RUN mkdir -p /app/logs /app/reports/generated

# The official evaluator mounts /input and /output at runtime. Running as root keeps
# the file contract robust when /output is owned by the host or harness.

ENTRYPOINT ["router"]
CMD ["submit-track1"]
