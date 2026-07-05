# Docker

Responsavel pela execucao reproduzivel.

## Objetivo

O projeto final precisa ser containerizado. Esta pasta vai concentrar:

- Dockerfile;
- compose opcional;
- entrypoint;
- exemplos de env vars;
- notas de execucao no ambiente padronizado.

## Env vars previstas

```bash
LOCAL_BASE_URL=http://localhost:8000/v1
LOCAL_MODEL=local-model
FIREWORKS_API_KEY=fw_...
FIREWORKS_BASE_URL=https://api.fireworks.ai/inference/v1
FIREWORKS_MODEL=accounts/fireworks/models/...
ROUTER_LOG_PATH=logs/run.jsonl
ROUTER_MODE=balanced
```

## Regra

O container nao deve depender de IP fixo, path local da maquina, dashboard, notebook ou estado manual.

