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

- [x] Rodar offline dataset completo.
- [x] Rodar policy comparison.
- [x] Rodar offline scoreboard.
- [x] Rodar prompt ablation.
- [x] Rodar trace analytics.
- [x] Rodar guardrail probes.
- [x] Comparar pelo menos 3 configuracoes.
- [x] Eleger configuracao candidata.
- [x] Registrar tradeoff accuracy vs token remoto.
- [x] Registrar riscos restantes.
- [x] Gerar battle report Markdown.
- [x] Gerar battle report JSON.
- [x] Integrar ao release check ou comando dedicado.

## Criterios de aceite

- Um unico comando gera o diagnostico competitivo.
- O relatorio mostra a melhor configuracao candidata.
- O relatorio mostra por que as alternativas perderam.
- O processo funciona sem AMD e sem Fireworks.

## Saida esperada

Um ritual de calibracao para transformar arquitetura em vantagem operacional.

## Evidencia local

```bash
python3 scripts/battle_drill.py
python3 -m unittest tests.test_battle_drill
scripts/offline_release_check.sh
```

## Decisao

O battle drill escolhe a configuracao candidata pelo scoreboard offline e coloca lado a lado policy comparison, policy ablation, prompt ablation, trace analytics e guardrail probes. Ele nao substitui o scoring oficial, mas cria um ritual repetivel para chegar no kickoff com uma hipotese forte.
