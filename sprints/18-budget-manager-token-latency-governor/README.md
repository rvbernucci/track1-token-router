# Sprint 18 - Budget Manager & Token-Latency Governor

## Tipo

Nao depende de credito.

## Objetivo

Criar um gerenciador de budget que controle custo remoto estimado, custo remoto real, latencia e limite de escalacao por task.

## Por que importa

O jogo do Track 1 e acertar gastando pouco. Sem budget manager, o sistema pode tomar decisoes corretas isoladamente e ainda perder no agregado.

## Entregaveis

- Modulo `router/orchestration/budget.py`.
- Contrato `TaskBudget`.
- Contrato `BudgetDecision`.
- Estimador offline de tokens remotos.
- Penalidade por latencia e parse failure.
- Integracao com o scoreboard offline.
- Testes de limites e edge cases.

## Checklist

- [x] Definir budget padrao por task.
- [x] Definir budget global por run.
- [x] Estimar tokens antes de chamada remota.
- [x] Registrar tokens reais depois de chamada remota.
- [x] Criar decisao `allow_remote`.
- [x] Criar decisao `deny_remote_budget_exceeded`.
- [x] Criar decisao `deny_remote_latency_risk`.
- [x] Penalizar parse failure no budget.
- [x] Integrar com `offline_score_simulator.py`.
- [x] Adicionar metricas no trace analytics.
- [x] Adicionar testes de estouro de token.
- [x] Adicionar testes de estouro de latencia.

## Criterios de aceite

- O runner sabe quando nao pode mais escalar.
- O custo remoto fica visivel antes e depois da decisao.
- O budget pode ser simulado sem Fireworks real.
- O scoreboard passa a comparar politicas tambem por disciplina de budget.

## Saida esperada

Um governador de custo que impede a arquitetura de vencer uma task e perder a competicao.

## Evidencia local

```bash
python3 -m unittest tests.test_budget_manager
python3 scripts/offline_score_simulator.py
python3 scripts/analyze_traces.py --logs fixtures/logs/sample-run.jsonl
scripts/offline_release_check.sh
```

## Decisao

O budget manager nasce como modulo deterministico e offline. Ele define decisoes `allow_remote`, `deny_remote_budget_exceeded` e `deny_remote_latency_risk`, registra gasto real e injeta penalidade por violacao no scoreboard. A policy engine da Sprint 19 passa a consumir esses sinais para decidir melhor.
