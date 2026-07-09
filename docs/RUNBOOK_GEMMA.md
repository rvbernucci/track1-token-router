# Runbook Gemma Local

## Objetivo

Usar Gemma como modelo de desenvolvimento, calibracao, demo e possivel caminho Fireworks permitido para M1, M2A e M2B via endpoint OpenAI-compatible.

Perfil recomendado: `runtime-profiles/gemma-local.env.example`.

Contexto Track 1: respostas locais corretas contam para accuracy e custam zero Fireworks tokens, mas o guia atual informa que o ambiente final tem `4 GB` RAM e `2 vCPU`. Portanto Gemma 26B/31B no AMD GPU pod e uma trilha de pesquisa/calibracao/demo, nao uma premissa para o container final. No scoring final, Gemma grande so deve entrar se aparecer em `ALLOWED_MODELS` e for chamado por `FIREWORKS_BASE_URL`, ou se o organizador fornecer explicitamente um endpoint local.

## AMD GPU Pod

Antes de rodar Gemma no pod AMD:

- criar ou entrar em um time no lablab.ai, mesmo competindo solo;
- aguardar ate 24 horas para alocacao do pod;
- acessar `https://notebooks.amd.com/hackathon`;
- lembrar que o uso do pod e limitado a 8 horas por 24 horas.

Se aparecer `team not registered`, o problema nao e codigo: falta criar/entrar no time.

Perfil observado em 2026-07-08 no ACT II:

- Ubuntu 22.04;
- Python 3.10.12;
- ROCm 7.2.1;
- 1 GPU AMD `gfx1100`;
- VRAM aproximada: 48 GiB;
- RAM aproximada: 503 GiB;
- workspace persistente com cerca de 93 GB livres.

Valide sempre o pod real antes de baixar pesos:

```bash
scripts/amd_pod_doctor.py
```

## Escolha inicial

- Comecar com um modelo Gemma grande apenas se a GPU e a latencia permitirem no pod de desenvolvimento.
- Em pod `gfx1100` com ~48 GiB, preferir quantizacao ou contexto menor antes de tentar Gemma 31B cheio.
- Reduzir contexto antes de trocar arquitetura.
- Trocar para modelo menor se houver OOM ou latencia alta.
- Nao usar embedding/RAG se a task oficial for pergunta livre sem base vetorial.

Para o container final:

- nao embutir Gemma 26B/31B;
- nao depender do notebook AMD estar disponivel no avaliador;
- se houver local model final, limitar a classe `2B-3B` 4-bit ou menor;
- se Gemma aparecer em `ALLOWED_MODELS`, chamar via Fireworks e medir tokens normalmente.

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
ROUTER_MODE=cascade python3 -m router eval \
  --jsonl evals/fireworks-pareto/track1-category-microbench.jsonl \
  --out reports/generated/gemma-track1-category-output.jsonl \
  --report reports/generated/gemma-track1-category-report.md
```

Depois testar o modo campeonato:

```bash
ROUTER_MODE=hybrid python3 -m router eval \
  --jsonl evals/fireworks-pareto/track1-category-microbench.jsonl \
  --out reports/generated/gemma-hybrid-track1-category-output.jsonl \
  --report reports/generated/gemma-hybrid-track1-category-report.md
```

## Limites

- Gemma grande pode ser bom demais para gastar em tarefas mecanicas no pod, por isso validadores e guardrails rodam antes.
- Modelo local nao deve decidir sobre conhecimento atual sem escalacao remota ou fonte confiavel.
- O scoring final informado usa `4 GB` RAM e `2 vCPU`; parametros do pod AMD nao transferem diretamente.
- Se a latencia local passar do limite por task, voltar para Fireworks-only ou reduzir modelo/quantizacao.
- Deterministicos devem ser apresentados como validadores/formatadores de seguranca, nao como o nucleo de inteligencia do agente.
