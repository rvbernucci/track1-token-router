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

- [ ] Mapear hipoteses de input: texto, JSON, JSONL, arquivo, stdin.
- [ ] Mapear hipoteses de output: texto puro, JSON, JSONL, arquivo.
- [ ] Mapear hipoteses de scoring: accuracy, token count, latency, parse failure.
- [ ] Mapear hipoteses de ambiente: container, env vars, rede, paths.
- [ ] Mapear proibicoes provaveis: stdout sujo, estado local, segredo em log.
- [ ] Criar lista de perguntas para kickoff.
- [ ] Criar fixture `scoring_text_batch`.
- [ ] Criar fixture `scoring_json_envelope`.
- [ ] Criar fixture `scoring_file_bundle`.
- [ ] Criar adapters experimentais para os tres formatos.
- [ ] Criar testes de parse e format.
- [ ] Criar drill cronometrado.
- [ ] Medir tempo de adaptacao por formato.
- [ ] Validar que o core nao importa adapters oficiais.
- [ ] Documentar plano de decisao no kickoff.

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
