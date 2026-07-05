# No-Credit Wave 3 Plan

Atualizado em: 2026-07-05

## Contexto

As Sprints 27-31 fecharam a segunda onda sem credito: demo estatica, reports publicos, adapter drill, latency/token envelope, artifact kit, policy optimizer e decision replay.

A terceira onda nao busca mais "mais arquitetura". Ela busca reduzir risco de contato com o mundo real:

- jurado precisa abrir uma URL;
- evaluator pode vir com lote grande ou formato estranho;
- modelo local real pode errar com confianca;
- respostas livres precisam de validacao melhor que exact match;
- logs publicos nao podem vazar detalhes sensiveis;
- submissao precisa ser ensaiada, nao improvisada.

## Principio de decisao

Cada sprint da onda 3 precisa melhorar pelo menos um destes eixos:

- publicabilidade;
- robustez contra modelo ruim;
- validacao de qualidade aberta;
- throughput e timeout;
- seguranca de artefatos compartilhaveis;
- prontidao operacional de submissao.

Se uma tarefa nao melhora nenhum desses eixos, ela fica fora da onda 3.

## Matriz das proximas sprints

| Sprint | Tema | Pergunta que responde | Principal artefato | Gate |
|---|---|---|---|---|
| 32 | Public Demo Deploy And Strict Readiness | Um jurado consegue abrir e entender o projeto por URL? | `docs/DEMO_DEPLOYMENT.md`, `scripts/check_demo_site.py` | strict readiness mais proximo do final |
| 33 | Bad Local Model Chaos Lab | O sistema barra um M1 bonito e errado? | `scripts/bad_local_model_drill.py` | false approval rate abaixo do limite |
| 34 | Semantic Validation Harness | Conseguimos medir qualidade livre sem LLM judge pago? | `scripts/run_semantic_eval.py` | semantic acceptable rate e classes de erro |
| 35 | Batch Throughput And Timeout Stress | O runner aguenta lote, deadline e falha parcial? | `scripts/batch_stress.py` | throughput/timeout dentro do envelope |
| 36 | Submission Rehearsal And Log Redaction | A submissao pode ser executada sem vazamento nem improviso? | `scripts/redact_logs.py`, `docs/SUBMISSION_REHEARSAL.md` | rehearsal report e redaction check |

## Dependencias

```text
Sprint 32 -> fecha URL publica e strict readiness
Sprint 33 -> usa fake provider e competition runner
Sprint 34 -> usa eval harness e final validator
Sprint 35 -> usa CLI run/eval, fake provider e latency envelope
Sprint 36 -> usa demo, reports, logs, final checklist e artifacts
```

Execucao recomendada:

1. Sprint 32 primeiro, porque remove uma pendencia real do strict mode.
2. Sprint 33 antes de mexer em prompts reais, porque testa confianca da cascata.
3. Sprint 34 depois do caos, porque cria melhor leitura de qualidade aberta.
4. Sprint 35 depois de qualidade, porque mede escala e deadline.
5. Sprint 36 por ultimo, porque consolida tudo em ensaio de submissao.

## O que cada sprint nao deve fazer

| Sprint | Anti-escopo |
|---|---|
| 32 | Criar backend, auth, banco ou dependencia de Native.Builder para runtime. |
| 33 | Otimizar para um modelo especifico inventado. |
| 34 | Fingir que rubrica deterministica equivale ao evaluator oficial. |
| 35 | Introduzir concorrencia antes de provar necessidade. |
| 36 | Publicar logs crus ou material que dependa de estado local privado. |

## Definition of Done da onda 3

- `demo_url` preenchido em `submission/final/submission-status.json`.
- Strict readiness falha somente por itens realmente finais ou passa com placeholders aprovados.
- Bad local model drill mede falsos aprovados.
- Semantic eval separa respostas aceitaveis, parciais e falhas.
- Batch stress mede throughput, timeout e falha parcial.
- Redaction check gera artefatos publicos seguros.
- Submission rehearsal gera roteiro executavel de ate 5 minutos.
- `scripts/offline_release_check.sh` continua verde.

## Risco residual mesmo apos a onda 3

- O evaluator oficial ainda pode revelar metricas diferentes.
- O modelo real na AMD Developer Cloud pode ter latencia/qualidade diferente do fake provider.
- Fireworks real pode ter custo/latencia distintos das estimativas.
- A distribuicao oficial pode ter tarefas fora do corpus offline.

Esses riscos passam para a trilha dependente de credito.
