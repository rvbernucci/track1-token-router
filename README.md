# Track 1 Token Router CLI

Projeto separado para o `Track 1 - Hybrid Token-Efficient Routing Agent`.

Objetivo: construir um runner headless, CLI-first, capaz de receber uma task em texto/arquivo/stdin/JSONL, executar a cascata local + Fireworks, registrar metricas e devolver uma resposta final limpa.

## Principio

Nao estamos construindo um app visual. Estamos construindo um runner competitivo.

Prioridades:

- stdout limpo para resposta final;
- logs estruturados separados;
- input adaptavel ao formato revelado no kickoff;
- modelo local e Fireworks configuraveis por env vars;
- container reproduzivel;
- minimo acoplamento com UI ou framework web.

## Pastas

| Pasta | Papel |
|---|---|
| [`core`](./core/README.md) | Logica da cascata: M1, M2A, M2B, Fireworks auditor, contratos e metricas. |
| [`cli`](./cli/README.md) | Comandos para interagir com o runner: `ask`, `solve`, `run`, `eval`. |
| [`adapters`](./adapters/README.md) | Entrada e saida: stdin, JSONL, arquivos, formato do evaluator. |
| [`logs`](./logs/README.md) | Logs locais JSONL, traces, tokens, rotas e resultados de runs. |
| [`docker`](./docker/README.md) | Container, imagem, env vars e comandos de execucao reproduzivel. |
| [`planning`](./planning/README.md) | Builder plan, principios, definition of done e estrategia-mestra. |
| [`sprints`](./sprints/README.md) | Plano operacional em 5 sprints com checklists e criterios de aceite. |

## Fluxo alvo

```text
TaskEnvelope
-> Modelo 1 local sem reasoning gera resposta livre
-> Modelo 2A local com reasoning valida em JSON pequeno
-> se approve: entrega resposta do Modelo 1
-> se escalate: Modelo 2B local com reasoning gera alternativa livre
-> Fireworks audita alternativa em approve-or-replace
-> resposta final limpa
```

## CLI alvo

```bash
router ask "What is 2+2?"
router ask --file ./task.txt
router solve --json < task.json
router run --jsonl ./tasks.jsonl --out ./runs/output.jsonl
router eval --jsonl ./tasks.jsonl --expected ./expected.jsonl
router eval --jsonl ./tasks.jsonl --expected ./expected.jsonl --report ./reports/generated/report.md
```

Regra importante:

- `stdout`: resposta final ou JSON final esperado pelo evaluator.
- `stderr`: mensagens humanas de debug.
- `logs/`: metricas e traces estruturados.

## Instalacao local

```bash
python3 -m pip install -e .
```

Tambem e possivel rodar sem instalar:

```bash
python3 -m router ask "What is 2+2?"
```

## Variaveis de ambiente

| Variavel | Padrao | Papel |
|---|---|---|
| `ROUTER_LOG_PATH` | `logs/run.jsonl` | Caminho dos logs estruturados JSONL. |
| `ROUTER_MODE` | `mock` | Modo de execucao: `mock`, `auto`, `local` ou `cascade`. |
| `LOCAL_BASE_URL` | vazio | Endpoint OpenAI-compatible do modelo local. |
| `LOCAL_MODEL` | vazio | Nome do modelo local. |
| `LOCAL_API_KEY` | vazio | API key opcional para endpoint local protegido. |
| `LOCAL_TIMEOUT_S` | `30` | Timeout por chamada local. |
| `LOCAL_MAX_RETRIES` | `1` | Tentativas extras em falha local. |
| `M1_TEMPERATURE` | `0.2` | Temperatura do gerador local M1. |
| `M1_MAX_TOKENS` | `512` | Limite de output do M1. |
| `M2A_TEMPERATURE` | `0.0` | Temperatura do verificador local M2A. |
| `M2A_MAX_TOKENS` | `256` | Limite de output do M2A. |
| `M2B_TEMPERATURE` | `0.2` | Temperatura do gerador local M2B. |
| `M2B_MAX_TOKENS` | `768` | Limite de output do M2B. |
| `FIREWORKS_BASE_URL` | `https://api.fireworks.ai/inference/v1` | Endpoint Fireworks OpenAI-compatible. |
| `FIREWORKS_MODEL` | vazio | Modelo remoto Fireworks. |
| `FIREWORKS_API_KEY` | vazio | API key Fireworks, usada apenas nas sprints remotas. |
| `FIREWORKS_TIMEOUT_S` | `60` | Timeout por chamada Fireworks. |
| `FIREWORKS_MAX_RETRIES` | `1` | Tentativas extras em falha Fireworks. |
| `FIREWORKS_TEMPERATURE` | `0.0` | Temperatura do auditor remoto. |
| `FIREWORKS_MAX_TOKENS` | `256` | Limite de output do auditor remoto. |

## Modo local M1

```bash
ROUTER_MODE=local \
LOCAL_BASE_URL=http://localhost:8000/v1 \
LOCAL_MODEL=local-model \
python3 -m router ask "What is 2+2?"
```

## Modo cascata local

```bash
ROUTER_MODE=cascade \
LOCAL_BASE_URL=http://localhost:8000/v1 \
LOCAL_MODEL=local-model \
python3 -m router ask "What is 2+2?"
```

## Modo hibrido com Fireworks

```bash
ROUTER_MODE=hybrid \
LOCAL_BASE_URL=http://localhost:8000/v1 \
LOCAL_MODEL=local-model \
FIREWORKS_API_KEY=fw_... \
FIREWORKS_MODEL=accounts/fireworks/models/... \
python3 -m router ask "What is 2+2?"
```

Nesse modo, Fireworks so e chamado quando o M2A escala a tarefa.
