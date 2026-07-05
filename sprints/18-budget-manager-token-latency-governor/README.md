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

- [ ] Definir budget padrao por task.
- [ ] Definir budget global por run.
- [ ] Estimar tokens antes de chamada remota.
- [ ] Registrar tokens reais depois de chamada remota.
- [ ] Criar decisao `allow_remote`.
- [ ] Criar decisao `deny_remote_budget_exceeded`.
- [ ] Criar decisao `deny_remote_latency_risk`.
- [ ] Penalizar parse failure no budget.
- [ ] Integrar com `offline_score_simulator.py`.
- [ ] Adicionar metricas no trace analytics.
- [ ] Adicionar testes de estouro de token.
- [ ] Adicionar testes de estouro de latencia.

## Criterios de aceite

- O runner sabe quando nao pode mais escalar.
- O custo remoto fica visivel antes e depois da decisao.
- O budget pode ser simulado sem Fireworks real.
- O scoreboard passa a comparar politicas tambem por disciplina de budget.

## Saida esperada

Um governador de custo que impede a arquitetura de vencer uma task e perder a competicao.

