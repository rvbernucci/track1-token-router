FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ROUTER_LOG_PATH=/app/logs/run.jsonl

WORKDIR /app

COPY pyproject.toml README.md ./
COPY router ./router
COPY evals ./evals
COPY logs ./logs

RUN pip install --no-cache-dir .

RUN useradd --create-home --shell /usr/sbin/nologin routeruser \
    && mkdir -p /app/logs /app/reports/generated \
    && chown -R routeruser:routeruser /app

USER routeruser

ENTRYPOINT ["router"]
CMD ["--help"]
