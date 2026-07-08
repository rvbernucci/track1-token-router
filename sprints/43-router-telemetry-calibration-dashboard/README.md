# Sprint 43 - Router Telemetry Calibration Dashboard

## Tipo

Nao depende de credito.

## Objetivo

Expor telemetria operacional do Pareto/Game Theory em relatorios e JSONL para calibracao: cada decisao deve revelar custo estimado, correlacao, payoff, label estrategico e motivo de escolha.

## Tese

Sem telemetria, nao existe calibracao. O roteador precisa deixar rastros compactos, seguros e comparaveis entre runs.

## Entregaveis

- Trace JSONL com campos de `game_theory`.
- Extensao de `router/analytics/traces.py` para decisao Fireworks.
- Relatorio `reports/generated/router-game-theory-dashboard.md`.
- Redaction de payloads sensiveis.
- Testes de schema de telemetria.

## Checklist

- [ ] Definir schema minimo de telemetria por task.
- [ ] Registrar `selected_model`, `domain`, `tier`, `nash_product`, `prisoner_payoff`, `game_label`.
- [ ] Registrar top 3 candidatos por score sem expor input completo.
- [ ] Agregar metricas por dominio/tier/modelo.
- [ ] Agregar contagem de labels: cooperate, defect, dominated, auxiliary.
- [ ] Gerar dashboard Markdown offline.
- [ ] Adicionar teste contra vazamento de segredo.
- [ ] Adicionar teste de compatibilidade com logs existentes.

## Metricas

- selected model distribution;
- average estimated cost;
- average Nash product;
- average prisoner payoff;
- over-escalation count;
- underqualification count;
- auxiliary exclusion count;
- redaction pass/fail.

## Definition Of Done

- Qualquer run offline gera dashboard auditavel.
- O dashboard explica por que os modelos foram chamados.
- Logs nao vazam segredo nem payload longo.
- `scripts/offline_release_check.sh` continua passando.

## Anti-Escopo

- Nao criar UI web.
- Nao logar respostas completas por padrao.
- Nao adicionar dependencia pesada de dashboard.
