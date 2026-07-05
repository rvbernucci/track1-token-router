# Runbook Fireworks Serverless

## Objetivo

Ativar Fireworks como auditor remoto compacto somente quando a cascata local escala.

Perfil recomendado: `runtime-profiles/fireworks-serverless.env.example`.

## Variaveis obrigatorias

- `FIREWORKS_API_KEY`: nunca commitar.
- `FIREWORKS_MODEL`: modelo permitido no hackathon.
- `FIREWORKS_BASE_URL`: `https://api.fireworks.ai/inference/v1`.

## Ativacao

```bash
cp runtime-profiles/fireworks-serverless.env.example .env.fireworks
printf "FIREWORKS_API_KEY=<set locally, not in git>\n" >> .env.fireworks.local
```

Carregar em shell local:

```bash
set -a
. ./.env.fireworks
. ./.env.fireworks.local
set +a
```

## Smoke

O modo hibrido exige endpoint local ativo.

```bash
ROUTER_MODE=hybrid \
python3 -m router ask "What is 2+2?" --json
```

Esperado para tarefa facil:

- rota local;
- `remote_tokens.total=0`.

Teste de escalacao controlada:

```bash
ROUTER_MODE=hybrid \
python3 -m router ask "Who is the CEO of AMD today?" --json
```

Esperado:

- chamada remota apenas se a cascata local escalar;
- resposta Fireworks em formato compacto `approve` ou `replace`;
- `remote_tokens` registrado.

## Budget guard

Antes de benchmark real:

```bash
export MAX_REMOTE_TOKENS_PER_TASK=300
export MAX_REMOTE_TOKENS_PER_RUN=6000
```

## Nao fazer

- Nao mandar todas as tasks direto para Fireworks sem medir.
- Nao aumentar `FIREWORKS_MAX_TOKENS` sem justificativa.
- Nao commitar `.env.fireworks.local`.
- Nao armazenar API key em logs ou screenshots.
