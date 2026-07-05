# Runbook vLLM OpenAI-Compatible

## Objetivo

Expor o modelo local como endpoint OpenAI-compatible para `LocalModelClient`.

Perfil recomendado: `runtime-profiles/amd-mi300x-vllm.env.example`.

## Variaveis importantes

- `VLLM_MODEL`: modelo ou caminho local.
- `VLLM_HOST`: usar `127.0.0.1` por seguranca.
- `VLLM_PORT`: padrao `8000`.
- `VLLM_TENSOR_PARALLEL_SIZE`: comecar em `1`.
- `VLLM_GPU_MEMORY_UTILIZATION`: comecar em `0.90`.
- `VLLM_MAX_MODEL_LEN`: reduzir se houver OOM.

## Comando base

```bash
python3 -m vllm.entrypoints.openai.api_server \
  --host "${VLLM_HOST:-127.0.0.1}" \
  --port "${VLLM_PORT:-8000}" \
  --model "${VLLM_MODEL}" \
  --served-model-name "${VLLM_SERVED_MODEL_NAME:-local-gemma}" \
  --tensor-parallel-size "${VLLM_TENSOR_PARALLEL_SIZE:-1}" \
  --gpu-memory-utilization "${VLLM_GPU_MEMORY_UTILIZATION:-0.90}" \
  --max-model-len "${VLLM_MAX_MODEL_LEN:-32768}"
```

Se a imagem AMD oferecer script proprio, usar o script oficial da imagem e preservar host, porta e served model.

## Health check

```bash
curl http://127.0.0.1:8000/v1/models
```

## Router smoke

```bash
LOCAL_BASE_URL=http://127.0.0.1:8000/v1 \
LOCAL_MODEL=local-gemma \
ROUTER_MODE=local \
python3 -m router ask "Say hello in one short sentence."
```

## OOM playbook

- Reduzir `VLLM_MAX_MODEL_LEN`.
- Reduzir batch/concurrency se configurado na imagem.
- Trocar para modelo menor.
- Confirmar que os pesos estao no scratch disk.

## Nao fazer

- Nao expor o endpoint sem auth em IP publico.
- Nao commitar `.env.amd-vllm`.
- Nao assumir que o scoring oficial tera a mesma GPU.
