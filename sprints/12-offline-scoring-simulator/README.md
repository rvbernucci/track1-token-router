# Sprint 12 - Offline Scoring Simulator

## Tipo

Nao depende de credito.

## Objetivo

Criar um simulador de scoring offline que combine qualidade simulada, tokens remotos, latencia e falhas de parsing para comparar politicas como se fossem competidores.

## Entregaveis

- Modulo de scoring offline.
- Script `scripts/offline_score_simulator.py`.
- Pesos configuraveis por CLI.
- Leaderboard Markdown e JSON.
- Testes cobrindo calculo de score e ordenacao.
- Integracao no release check offline.

## Checklist

- [x] Criar `router/evals/scoring.py`.
- [x] Definir formula de score offline.
- [x] Incluir accuracy simulada.
- [x] Penalizar tokens remotos simulados.
- [x] Penalizar latencia simulada.
- [x] Penalizar parse failures.
- [x] Criar script `scripts/offline_score_simulator.py`.
- [x] Gerar `reports/generated/offline-scoreboard.md`.
- [x] Gerar `reports/generated/offline-scoreboard.json`.
- [x] Adicionar testes de score.
- [x] Documentar pesos e interpretacao.
- [x] Integrar no `scripts/offline_release_check.sh`.

## Criterios de aceite

- O simulador roda sem AMD e sem Fireworks.
- O leaderboard compara `aggressive`, `balanced` e `conservative`.
- A formula e explicita e testada.
- O release check offline continua passando.

## Saida esperada

Um placar offline que ajuda a escolher politica antes de ter creditos reais.

## Evidencia local

```bash
python3 scripts/offline_score_simulator.py
python3 -m unittest tests.test_offline_scoring
scripts/offline_release_check.sh
```

## Formula

```text
score = exact_match_rate * accuracy_weight
  - remote_tokens_total * remote_token_weight
  - latency_ms_total * latency_ms_weight
  - parse_failures * parse_failure_weight
```

Pesos padrao:

- `accuracy_weight=1000.0`
- `remote_token_weight=0.02`
- `latency_ms_weight=0.001`
- `parse_failure_weight=25.0`
