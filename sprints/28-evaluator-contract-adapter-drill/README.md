# Sprint 28 - Evaluator Contract And Adapter Drill

## Tipo

Nao depende de credito.

## Objetivo

Criar uma matriz explicita de hipoteses do evaluator oficial e praticar a adaptacao rapida de novos formatos de input/output antes do kickoff.

## Por que importa

O maior risco tecnico sem credito nao e modelo. E contrato. Se o evaluator oficial vier com envelope inesperado, arquivo, schema diferente ou output rigido, precisamos adaptar em minutos.

## Tese

O core deve continuar falando `TaskEnvelope` e `AnswerResult`. Toda surpresa oficial deve ser isolada em adapters, fixtures e testes.

## Entregaveis

- `docs/EVALUATOR_ASSUMPTIONS.md`.
- `docs/KICKOFF_ADAPTER_DRILL.md`.
- `fixtures/adapter-drill/`.
- Pelo menos tres formatos simulados de evaluator.
- Adapters experimentais em `router/adapters/official/`.
- Testes de round-trip para cada formato.
- Script `scripts/adapter_drill.py`.
- Relatorio `reports/generated/adapter-drill-report.md`.

## Checklist

- [x] Mapear hipoteses de input: texto, JSON, JSONL, arquivo, stdin.
- [x] Mapear hipoteses de output: texto puro, JSON, JSONL, arquivo.
- [x] Mapear hipoteses de scoring: accuracy, token count, latency, parse failure.
- [x] Mapear hipoteses de ambiente: container, env vars, rede, paths.
- [x] Mapear proibicoes provaveis: stdout sujo, estado local, segredo em log.
- [x] Criar lista de perguntas para kickoff.
- [x] Criar fixture `scoring_text_batch`.
- [x] Criar fixture `scoring_json_envelope`.
- [x] Criar fixture `scoring_file_bundle`.
- [x] Criar adapters experimentais para os tres formatos.
- [x] Criar testes de parse e format.
- [x] Criar drill cronometrado.
- [x] Medir tempo de adaptacao por formato.
- [x] Validar que o core nao importa adapters oficiais.
- [x] Documentar plano de decisao no kickoff.

## Criterios de aceite

- Cada hipotese tem impacto, mitigacao e teste local.
- Cada formato simulado tem fixture, adapter e teste.
- O drill mostra tempo alvo menor que 30 minutos por adapter simples.
- A adaptacao nao altera `router/core/*`.
- `stdout` continua limpo nos caminhos simulados.

## Metricas

- Tempo de adapter por formato.
- Numero de alteracoes fora de `router/adapters/official`.
- Taxa de round-trip dos fixtures.
- Numero de perguntas de kickoff ainda abertas.

## Comandos esperados

```bash
python3 scripts/adapter_drill.py --report reports/generated/adapter-drill-report.md
python3 -m unittest tests.test_official_adapters
```

## Riscos

- Superotimizar para formatos inventados.
- Criar adapters que vazam detalhes oficiais para o core.
- Esquecer output formatting e testar so input parsing.

## Decisao

Adapters sao camada de borda. O core competitivo nao deve saber se a entrada veio de texto, JSON, JSONL, zip ou dashboard oficial.

## Definition of Done

- Matriz de evaluator existe.
- Drill de adapter existe.
- Tres formatos simulados estao testados.
- Tempo de adaptacao foi medido.
- Perguntas de kickoff foram documentadas.

## Evidencias

- `docs/EVALUATOR_ASSUMPTIONS.md` documenta hipoteses, impacto, mitigacao, testes e perguntas de kickoff.
- `docs/KICKOFF_ADAPTER_DRILL.md` define o procedimento de adaptacao em menos de 30 minutos.
- `fixtures/adapter-drill/` contem `scoring_text_batch`, `scoring_json_envelope` e `scoring_file_bundle`.
- `router/adapters/official/` contem adapters experimentais para os tres formatos.
- `scripts/adapter_drill.py --check` gera `reports/generated/adapter-drill-report.md`.
- `tests/test_official_adapters.py` cobre parse e format dos tres formatos.
- `scripts/offline_release_check.sh` executa o drill antes do battle drill.
