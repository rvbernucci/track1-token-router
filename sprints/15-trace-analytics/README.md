# Sprint 15 - Trace Analytics

## Tipo

Nao depende de credito.

## Objetivo

Transformar logs JSONL em relatorios de rotas, latencia, tokens, erros e regressao para calibrar o roteador.

## Entregaveis

- Modulo `router/analytics/traces.py`.
- Script `scripts/analyze_traces.py`.
- Relatorio Markdown e JSON.
- Fixtures de logs.
- Testes de agregacao.
- Integracao opcional no release check.

## Checklist

- [x] Ler `logs/*.jsonl`.
- [x] Agregar por rota.
- [x] Agregar tokens remotos.
- [x] Agregar latencia por etapa.
- [x] Contar erros e parse failures.
- [x] Detectar run vazio.
- [x] Gerar relatorio Markdown.
- [x] Gerar JSON.
- [x] Adicionar fixtures de logs.
- [x] Adicionar testes.

## Criterios de aceite

- Um log JSONL vira relatorio util.
- O script tolera arquivos ausentes/vazios.
- O relatorio ajuda a calibrar politica e prompt.
- Nao exige credenciais.

## Saida esperada

Uma lente operacional para entender como o roteador esta se comportando.

## Evidencia local

```bash
python3 scripts/analyze_traces.py --logs fixtures/logs/sample-run.jsonl
python3 -m unittest tests.test_trace_analytics
scripts/offline_release_check.sh
```

## Decisao

O script tolera `logs/*.jsonl` vazio ou ausente, porque os logs reais sao artefatos locais ignorados pelo Git. O release check usa `fixtures/logs/sample-run.jsonl` para validar comportamento reproduzivel.
