# Runbook Gemma Local

## Objetivo

Usar Gemma como modelo local para M1, M2A e M2B via endpoint OpenAI-compatible.

Perfil recomendado: `runtime-profiles/gemma-local.env.example`.

## Escolha inicial

- Comecar com um modelo Gemma grande apenas se a GPU e a latencia permitirem.
- Reduzir contexto antes de trocar arquitetura.
- Trocar para modelo menor se houver OOM ou latencia alta.
- Nao usar embedding/RAG se a task oficial for pergunta livre sem base vetorial.

## Prompt/runtime

O router fala com o endpoint via API OpenAI-compatible. O servidor local fica responsavel por aplicar o formato correto do modelo.

Variaveis:

- `LOCAL_MODEL`: nome exposto pelo servidor local.
- `GEMMA_PROMPT_FORMAT`: anotacao operacional, nao lida pelo runtime atual.
- `M1_*`, `M2A_*`, `M2B_*`: temperaturas e limites de output.

## Smoke local

```bash
cp runtime-profiles/gemma-local.env.example .env.gemma-local
set -a
. ./.env.gemma-local
set +a
python3 -m router ask "Return exactly GEMMA_OK and nothing else." --json
```

Esperado:

- guardrail ou solver responde antes do modelo quando aplicavel;
- caso livre chama endpoint local;
- logs mostram rota e latencias locais.

## Calibracao minima

```bash
python3 -m router eval \
  --jsonl evals/fuzz/tasks.jsonl \
  --expected evals/fuzz/expected.jsonl \
  --out reports/generated/gemma-fuzz-output.jsonl \
  --report reports/generated/gemma-fuzz-report.md
```

## Limites

- Gemma grande pode ser bom demais para gastar em tarefas mecanicas, por isso solvers e guardrails rodam antes.
- Modelo local nao deve decidir sobre conhecimento atual sem escalacao remota ou fonte confiavel.
- Se o scoring final usar outro hardware, os parametros locais precisam ser recalibrados.
