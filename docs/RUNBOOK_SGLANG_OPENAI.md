# Runbook SGLang OpenAI-Compatible

## Objetivo

Usar SGLang como alternativa OpenAI-compatible para o modelo local.

Perfil recomendado: `runtime-profiles/amd-mi300x-sglang.env.example`.

## Variaveis importantes

- `SGLANG_MODEL`: modelo ou caminho local.
- `SGLANG_HOST`: usar `127.0.0.1`.
- `SGLANG_PORT`: padrao `30000`.
- `SGLANG_TP_SIZE`: comecar em `1`.
- `SGLANG_MEM_FRACTION_STATIC`: reduzir se houver OOM.
- `SGLANG_CONTEXT_LENGTH`: reduzir se houver OOM.

## Comando base

```bash
python3 -m sglang.launch_server \
  --host "${SGLANG_HOST:-127.0.0.1}" \
  --port "${SGLANG_PORT:-30000}" \
  --model-path "${SGLANG_MODEL}" \
  --served-model-name "${SGLANG_SERVED_MODEL_NAME:-local-gemma}" \
  --tp-size "${SGLANG_TP_SIZE:-1}" \
  --mem-fraction-static "${SGLANG_MEM_FRACTION_STATIC:-0.85}" \
  --context-length "${SGLANG_CONTEXT_LENGTH:-32768}"
```

Se a imagem AMD/DigitalOcean tiver wrapper proprio, usar o wrapper e manter a porta OpenAI-compatible.

## Health check

```bash
curl http://127.0.0.1:30000/v1/models
```

## Router smoke

```bash
LOCAL_BASE_URL=http://127.0.0.1:30000/v1 \
LOCAL_MODEL=local-gemma \
ROUTER_MODE=local \
python3 -m router ask "Say hello in one short sentence."
```

## Quando preferir SGLang

- vLLM indisponivel na imagem.
- Melhor latencia no modelo escolhido.
- Melhor estabilidade com o contexto desejado.

## Nao fazer

- Nao trocar vLLM por SGLang durante benchmark sem registrar a mudanca.
- Nao deixar porta `30000` publica.
- Nao commitar logs com prompts sensiveis.
