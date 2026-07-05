# Sprint 21 - Calibration Loop & Battle Drill

## Tipo

Nao depende de credito.

## Objetivo

Criar um loop de calibracao que rode datasets, compare politicas, ajuste thresholds e produza um battle report antes do kickoff/scoring real.

## Por que importa

Depois que a orquestracao existir, a vantagem vem de iterar rapido. Precisamos de um ritual de competicao: rodar, medir, ajustar e repetir.

## Entregaveis

- Script `scripts/battle_drill.py`.
- Relatorio `reports/generated/battle-report.md`.
- JSON `reports/generated/battle-report.json`.
- Comparacao de configuracoes.
- Ranking por score offline.
- Checklist de readiness.
- Testes do pipeline de calibracao.

## Checklist

- [ ] Rodar offline dataset completo.
- [ ] Rodar policy comparison.
- [ ] Rodar offline scoreboard.
- [ ] Rodar prompt ablation.
- [ ] Rodar trace analytics.
- [ ] Rodar guardrail probes.
- [ ] Comparar pelo menos 3 configuracoes.
- [ ] Eleger configuracao candidata.
- [ ] Registrar tradeoff accuracy vs token remoto.
- [ ] Registrar riscos restantes.
- [ ] Gerar battle report Markdown.
- [ ] Gerar battle report JSON.
- [ ] Integrar ao release check ou comando dedicado.

## Criterios de aceite

- Um unico comando gera o diagnostico competitivo.
- O relatorio mostra a melhor configuracao candidata.
- O relatorio mostra por que as alternativas perderam.
- O processo funciona sem AMD e sem Fireworks.

## Saida esperada

Um ritual de calibracao para transformar arquitetura em vantagem operacional.

