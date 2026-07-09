FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ROUTER_LOG_PATH=/app/logs/run.jsonl \
    ROUTER_MODE=fireworks \
    FIREWORKS_MATRIX_WEIGHTS=/app/router/data/fireworks_track1_allowed_weights.json \
    FIREWORKS_TIMEOUT_S=24 \
    FIREWORKS_MAX_RETRIES=0 \
    ENABLE_GUARDRAILS=1 \
    ENABLE_ORCHESTRATOR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY router ./router
COPY evals ./evals
COPY logs ./logs

RUN pip install --no-cache-dir .

RUN mkdir -p /app/logs /app/reports/generated

# The official evaluator mounts /input and /output at runtime. Running as root keeps
# the file contract robust when /output is owned by the host or harness.

ENTRYPOINT ["router"]
CMD ["submit-track1"]
