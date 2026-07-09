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

## Quickstart limpo

Do zero, use virtualenv. O projeto suporta Python `3.10+`, que cobre o pod AMD observado no hackathon. Em macOS/Homebrew, `python3 -m pip install -e .` fora de uma venv pode falhar por PEP 668.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
router ask "What is 2+2?"
```

Sem instalacao local, tambem funciona:

```bash
python3 -m router ask "What is 2+2?"
```

Checks principais:

```bash
python3 -m unittest discover -s tests
python3 scripts/track1_deterministic_coverage.py --check
python3 scripts/competition_submission_audit.py --skip-network
scripts/offline_release_check.sh
python3 scripts/secret_scan.py
git diff --check
```

Atalhos equivalentes:

```bash
make setup
make smoke
make test
make deterministic-coverage
make submission-audit
make release-check
make doctor
```

No AMD Developer Cloud/Jupyter pod:

```bash
git clone https://github.com/rvbernucci/track1-token-router.git
cd track1-token-router
scripts/amd_pod_doctor.py
SKIP_TESTS=1 scripts/bootstrap_amd_pod.sh
```

Contrato oficial Track 1 em modo offline:

```bash
ROUTER_MODE=mock \
python3 -m router submit-track1 \
  --input fixtures/official/lablab_track1_tasks.json \
  --output reports/generated/official-smoke-results.json
```

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
| [`docs/COMPETITION_GAP_ANALYSIS.md`](./docs/COMPETITION_GAP_ANALYSIS.md) | Lacunas restantes sem credito e trilha de Sprints 22-26. |
| [`docs/NEXT_NO_CREDIT_IMPROVEMENTS.md`](./docs/NEXT_NO_CREDIT_IMPROVEMENTS.md) | Terceira onda sem credito: deploy publico, caos de modelo local, validacao semantica, batch stress e redaction. |
| [`docs/NO_CREDIT_WAVE_3_PLAN.md`](./docs/NO_CREDIT_WAVE_3_PLAN.md) | Plano executivo das Sprints 32-36, com dependencias, gates e anti-escopo. |

## Roadmap atual

A rota principal do projeto nao depende de creditos AMD ou Fireworks.

Enquanto os creditos nao chegam, seguimos nas sprints offline. As sprints 06-21 ja criaram dataset, simuladores, testes, scoring, guardrails, analytics, release automation, state machine, budget manager, policy engine, prompt packet, final validator e battle drill.

A primeira trilha de readiness competitivo sem credito foi fechada:

- Sprint 22: competition mode integration.
- Sprint 23: official input fuzz pack.
- Sprint 24: deterministic solver pack.
- Sprint 25: platform runbooks e runtime profiles.
- Sprint 26: submission readiness kit.

A segunda trilha de readiness tambem foi fechada:

- Sprint 27: static demo e public reports.
- Sprint 28: evaluator contract e adapter drill.
- Sprint 29: latency/token envelope.
- Sprint 30: artifact build kit.
- Sprint 31: policy Pareto e decision replay.

O proximo bloco sem credito e a terceira onda:

- Sprint 32: public demo deploy e strict readiness.
- Sprint 33: bad local model chaos lab.
- Sprint 34: semantic validation harness.
- Sprint 35: batch throughput e timeout stress.
- Sprint 36: submission rehearsal e log redaction.

O proximo bloco recomendado esta em [`docs/NEXT_NO_CREDIT_IMPROVEMENTS.md`](./docs/NEXT_NO_CREDIT_IMPROVEMENTS.md).

Quando os creditos chegarem, entramos na trilha paralela `credit-gated`:

- Credit A: AMD runtime bring-up.
- Credit B: Fireworks real audit calibration.
- Credit C: end-to-end cost benchmark.
- Credit D: final cloud submission drill.

Detalhes em [`sprints`](./sprints/README.md).

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
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

Tambem e possivel rodar sem instalar:

```bash
python3 -m router ask "What is 2+2?"
```

## Variaveis de ambiente

| Variavel | Padrao | Papel |
|---|---|---|
| `ROUTER_LOG_PATH` | `logs/run.jsonl` | Caminho dos logs estruturados JSONL. |
| `ROUTER_MODE` | `mock` | Modo de execucao: `mock`, `auto`, `local`, `cascade`, `hybrid`, `competition` ou `fireworks`. |
| `ROUTER_POLICY` | `balanced` | Politica de roteamento: `aggressive`, `balanced` ou `conservative`. |
| `LOCAL_BASE_URL` | vazio | Endpoint OpenAI-compatible do modelo local. |
| `ENABLE_GUARDRAILS` | `0` | Liga regras deterministicas conservadoras antes do runner. |
| `ENABLE_ORCHESTRATOR` | `0` | Liga trace de state machine em torno do runner. |
| `COMPETITION_DRY_RUN` | `1` | Mantem `ROUTER_MODE=competition` sem chamadas reais de modelo remoto/local por padrao. |
| `MAX_REMOTE_TOKENS_PER_TASK` | `300` | Budget remoto simulado por task. |
| `MAX_REMOTE_TOKENS_PER_RUN` | `6000` | Budget remoto simulado por run offline. |
| `MAX_REMOTE_LATENCY_MS` | `3000` | Limite de risco de latencia remota por decisao. |
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
| `ALLOWED_MODELS` | vazio | Lista oficial de modelos permitidos injetada pelo harness ACT II; aceita CSV, espacos/quebras de linha ou JSON array. |
| `FIREWORKS_MODEL` | vazio | Override local; se vazio, usa o primeiro item de `ALLOWED_MODELS`. |
| `FIREWORKS_API_KEY` | vazio | API key Fireworks, usada apenas nas sprints remotas. |
| `FIREWORKS_TIMEOUT_S` | `24` | Timeout por chamada Fireworks, mantido abaixo do limite oficial de 30s por request. |
| `FIREWORKS_MAX_RETRIES` | `0` | Tentativas extras em falha Fireworks; no Track 1 evitamos cascata lenta por retry. |
| `FIREWORKS_TEMPERATURE` | `0.0` | Temperatura do auditor remoto. |
| `FIREWORKS_MAX_TOKENS` | `256` | Limite de output do auditor remoto. |
| `FIREWORKS_SERVICE_TIER` | vazio | Vazio usa Standard; `priority` deve ser usado apenas como fallback manual de confiabilidade. |
| `FIREWORKS_MATRIX_WEIGHTS` | vazio localmente; `/app/router/data/fireworks_track1_allowed_weights.json` no Docker | Caminho para pesos calibrados por microbench; quando presente, os runners Fireworks e hibrido usam regressao matricial + Nash para escolher o modelo. |
| `TRACK1_MAX_RUNTIME_S` | `570` | Orçamento total do comando `submit-track1`, deixando margem abaixo dos 10 minutos oficiais. |
| `TRACK1_RUNTIME_RESERVE_S` | `5` | Reserva final para escrever JSON valido em `/output/results.json` antes do limite. |

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
FIREWORKS_API_KEY=<fireworks-api-key> \
FIREWORKS_MODEL=accounts/fireworks/models/... \
python3 -m router ask "What is 2+2?"
```

Nesse modo, Fireworks so e chamado quando o M2A escala a tarefa.

No Track 1 atual, esse e o modo campeonato quando ha um modelo local confiavel: respostas locais corretas contam para accuracy e usam zero Fireworks tokens. Se nao houver endpoint local estavel no ambiente final, use `ROUTER_MODE=fireworks`.

## Modo oficial Fireworks direto

```bash
ROUTER_MODE=fireworks \
FIREWORKS_API_KEY=<harness-key> \
FIREWORKS_BASE_URL=<harness-base-url> \
ALLOWED_MODELS=accounts/fireworks/models/... \
python3 -m router submit-track1 --input /input/tasks.json --output /output/results.json
```

Esse modo implementa o contrato oficial ACT II: le `/input/tasks.json`, escreve `/output/results.json`, usa solvers deterministicos antes de Fireworks e escolhe entre modelos de `ALLOWED_MODELS` por tier de tarefa.

No Docker de submissao, `FIREWORKS_MATRIX_WEIGHTS` ja aponta para `router/data/fireworks_track1_allowed_weights.json`, treinado com microbench real dos modelos permitidos Track 1 em 2026-07-09. A politica atual combina regressao ridge, Nash welfare, eficiencia de tokens, tokens observados por dominio/estrutura/modelo e risco empirico: quando a validade observada e comparavel, `kimi-k2p7-code` tende a vencer por usar menos tokens Fireworks; `minimax-m3` permanece como fallback competitivo em dominios e estruturas onde robustez empirica supera a economia de tokens.

Para usar calibracao por microbench:

```bash
python3 scripts/fit_fireworks_matrix_regression.py \
  --dataset evals/fireworks-pareto/track1-category-microbench.jsonl \
  --results reports/generated/fireworks-track1-category-20260709-results.jsonl
ROUTER_MODE=fireworks \
FIREWORKS_MATRIX_WEIGHTS=router/data/fireworks_track1_allowed_weights.json \
FIREWORKS_API_KEY=<harness-key> \
ALLOWED_MODELS=minimax-m3,kimi-k2p7-code,gemma-4-31b-it,gemma-4-26b-a4b-it,gemma-4-31b-it-nvfp4 \
python3 -m router ask "Summarise token-efficient routing in one sentence."
```

Em clone limpo, o `fit` usa `evals/fireworks-pareto/seed-microbench-results.jsonl` como seed offline. Depois de rodar microbench real com creditos Fireworks, os resultados em `reports/generated/fireworks-microbench-*.jsonl` passam a alimentar pesos mais fortes.

## Modo competicao dry-run

```bash
ROUTER_MODE=competition \
COMPETITION_DRY_RUN=1 \
python3 -m router ask "What is 10 + 5? Return only the number."
```

Esse modo integra guardrails, sinais de risco, budget, policy engine, prompt packet, state trace e validacao final sem consumir creditos por padrao.

## Docker

Build:

```bash
docker build -t track1-token-router .
```

Smoke test:

```bash
docker run --rm track1-token-router --help
docker run --rm -e ROUTER_MODE=mock track1-token-router ask "What is 2+2?"
```

Official Track 1 file contract:

```bash
mkdir -p /tmp/track1-input /tmp/track1-output
cp fixtures/official/lablab_track1_tasks.json /tmp/track1-input/tasks.json
docker run --rm \
  -e ROUTER_MODE=mock \
  -v /tmp/track1-input:/input:ro \
  -v /tmp/track1-output:/output \
  track1-token-router
```

Run JSONL:

```bash
docker run --rm \
  -v "$PWD/reports/generated:/app/reports/generated" \
  track1-token-router eval \
  --jsonl evals/golden/tasks.jsonl \
  --expected evals/golden/expected.jsonl \
  --out reports/generated/golden-output.jsonl \
  --report reports/generated/golden-report.md
```

Hybrid run:

```bash
docker run --rm \
  -e ROUTER_MODE=hybrid \
  -e LOCAL_BASE_URL=http://host.docker.internal:8000/v1 \
  -e LOCAL_MODEL=local-model \
  -e FIREWORKS_API_KEY="$FIREWORKS_API_KEY" \
  -e FIREWORKS_MODEL=accounts/fireworks/models/replace-me \
  track1-token-router ask "What is 2+2?"
```

## Avaliacao local

```bash
scripts/verify.sh
```

Esse script roda:

- suite de testes;
- smoke test do CLI;
- eval do golden set;
- validacao do offline evaluation arena;
- eval offline por categoria;
- relatorio Markdown em `reports/generated/golden-report.md`.

Eval offline direto:

```bash
python3 scripts/generate_offline_eval.py --check
python3 -m router eval \
  --jsonl evals/offline/tasks.jsonl \
  --expected evals/offline/expected.jsonl \
  --report reports/generated/offline-report.md
```

Comparacao offline de politicas:

```bash
python3 scripts/compare_policies.py \
  --jsonl evals/offline/tasks.jsonl \
  --expected evals/offline/expected.jsonl \
  --report reports/generated/policy-comparison.md
```

Scoreboard offline:

```bash
python3 scripts/offline_score_simulator.py \
  --jsonl evals/offline/tasks.jsonl \
  --expected evals/offline/expected.jsonl \
  --report reports/generated/offline-scoreboard.md
```

Formula usada no simulador:

```text
score = exact_match_rate * accuracy_weight
  - remote_tokens_total * remote_token_weight
  - latency_ms_total * latency_ms_weight
  - parse_failures * parse_failure_weight
```

Prompt ablation offline:

```bash
python3 scripts/prompt_ablation.py --check \
  --manifest prompts/manifest.json \
  --report reports/generated/prompt-ablation.md
```

Guardrails deterministicos opcionais:

```bash
ENABLE_GUARDRAILS=1 python3 -m router ask "What is 12 - 5? Return only the number."
```

As regras sao conservadoras e cobrem apenas input vazio, saudacoes simples, soma/subtracao triviais e eco literal. Qualquer caso ambiguo segue para o runner normal.

Trace analytics offline:

```bash
python3 scripts/analyze_traces.py \
  --logs "logs/*.jsonl" \
  --report reports/generated/trace-summary.md
```

State machine report:

```bash
python3 scripts/state_machine_report.py \
  --report reports/generated/state-machine-report.md
```

Adaptive policy ablation:

```bash
python3 scripts/policy_ablation.py \
  --jsonl evals/offline/tasks.jsonl \
  --report reports/generated/policy-ablation.md
```

O scoreboard tambem estima `remote_packet_tokens`, isto e, o tamanho do pacote compacto que iria ao auditor remoto.

Battle drill offline:

```bash
python3 scripts/battle_drill.py \
  --report reports/generated/battle-report.md \
  --out-json reports/generated/battle-report.json
```

Release notes dry-run:

```bash
python3 scripts/generate_release_notes.py \
  --tag offline-dry-run \
  --output reports/generated/release-notes.md
```

Publicacao GHCR fica em `.github/workflows/release.yml` e acontece apenas em tags `v*` ou `offline-*`.

Audit final da submissao, sem depender de Docker local:

```bash
python3 scripts/competition_submission_audit.py --skip-network
python3 scripts/competition_submission_audit.py \
  --image ghcr.io/rvbernucci/track1-token-router:offline-rc-20260709-1242 \
  --expected-revision 5b45745cc48ac831e70a6d11429f4737414059eb \
  --expected-version offline-rc-20260709-1242
```

O primeiro comando valida contrato oficial, release workflow, README e gates offline. O segundo consulta o GHCR diretamente e confirma que a imagem final e publica, tem manifesto `linux/amd64`, fica abaixo do limite de 10GB e carrega labels OCI de commit/tag.

## Estrategia de token efficiency

- M1 tenta responder localmente com formato livre.
- M2A valida localmente com uma decisao curta `approve/escalate`.
- Tarefas aprovadas por M2A saem com zero token remoto.
- Tarefas escaladas passam por M2B local antes de Fireworks.
- Fireworks recebe um pacote compacto e audita M2B com `approve/replace`.
- Completion remota tende a ser pequena porque `approve` devolve `answer=""`.

## Tradeoffs

- Escalar pouco economiza tokens, mas aumenta risco de erro.
- Escalar demais melhora seguranca, mas pode perder no custo.
- M2A e o ponto de calibracao mais importante.
- Logs guardam respostas candidatas para analise local; nao use dados sensiveis nos evals publicos.
- O golden set usa exact match simples, suficiente para regressao, mas limitado para avaliar qualidade aberta.

## Limites conhecidos

- O formato oficial das tasks pode mudar no kickoff.
- A qualidade final depende do modelo local disponivel na AMD Developer Cloud.
- O modo `hybrid` exige um endpoint local OpenAI-compatible e credenciais Fireworks.
- O projeto e CLI/headless de proposito; UI fica fora do caminho critico de scoring.

## Submissao

Leia [`SUBMISSION.md`](./SUBMISSION.md) para a narrativa tecnica, estrategia e pitch curto.

O sync mais recente com a pagina oficial da competicao esta em [`docs/OFFICIAL_COMPETITION_SYNC.md`](./docs/OFFICIAL_COMPETITION_SYNC.md).

## Chaos lab sem credito

O fake provider permite simular local model e Fireworks sem chaves reais:

```bash
python3 -m router.dev.fake_provider --help
```

Guia completo em [`docs/CHAOS_LAB.md`](./docs/CHAOS_LAB.md).

## Kickoff adapters

Quando o formato oficial aparecer, use:

- [`KICKOFF_CHECKLIST.md`](./KICKOFF_CHECKLIST.md)
- [`router/adapters/official`](./router/adapters/official/README.md)
- [`fixtures/official`](./fixtures/official)

## Cultura de testes

Use `playground/` para experimentos rapidos no estilo de um `test.ts` e `tests/` para garantias automatizadas:

```bash
python3 playground/test_policy_logic.py
python3 scripts/list_test_coverage.py --check
```

Guia completo em [`docs/TESTING_CULTURE.md`](./docs/TESTING_CULTURE.md) e matriz em [`docs/TEST_MATRIX.md`](./docs/TEST_MATRIX.md).
