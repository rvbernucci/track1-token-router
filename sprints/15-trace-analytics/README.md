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

- [ ] Ler `logs/*.jsonl`.
- [ ] Agregar por rota.
- [ ] Agregar tokens remotos.
- [ ] Agregar latencia por etapa.
- [ ] Contar erros e parse failures.
- [ ] Detectar run vazio.
- [ ] Gerar relatorio Markdown.
- [ ] Gerar JSON.
- [ ] Adicionar fixtures de logs.
- [ ] Adicionar testes.

## Criterios de aceite

- Um log JSONL vira relatorio util.
- O script tolera arquivos ausentes/vazios.
- O relatorio ajuda a calibrar politica e prompt.
- Nao exige credenciais.

## Saida esperada

Uma lente operacional para entender como o roteador esta se comportando.

