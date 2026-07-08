# Sprint 42 - Nash Payoff Replay Lab

## Tipo

Nao depende de credito.

## Objetivo

Construir um laboratorio de replay para comparar estrategias de selecao: menor custo puro, Pareto antigo, Nash welfare, conservative-quality e oracle esperado por fixture.

## Tese

Nao basta o Nash parecer elegante. Precisamos provar que ele melhora o tradeoff contra baselines simples e que nao cria regressao em cheap tasks.

## Entregaveis

- `scripts/replay_model_selection_strategies.py`.
- Baselines: `cheapest`, `pareto_cost_first`, `nash_welfare`, `quality_first`.
- Relatorio `reports/generated/nash-payoff-replay.md`.
- Tabela de payoff por estrategia.
- Testes de regressao para cenarios criticos.

## Checklist

- [ ] Extrair candidatos e scores sem chamar Fireworks.
- [ ] Implementar replay de estrategia `cheapest`.
- [ ] Implementar replay de estrategia `pareto_cost_first`.
- [ ] Implementar replay de estrategia `nash_welfare`.
- [ ] Implementar replay de estrategia `quality_first`.
- [ ] Comparar custo estimado total por estrategia.
- [ ] Comparar violacoes de accuracy proxy por estrategia.
- [ ] Comparar over-escalation por estrategia.
- [ ] Criar relatorio Markdown com tabela e conclusao.
- [ ] Adicionar teste para garantir que `nash_welfare` nao escolhe candidato underqualified.

## Metricas

- estimated total cost;
- expected accuracy proxy;
- over-escalation count;
- underqualification count;
- average Nash product;
- prisoner payoff medio;
- modelos escolhidos por dominio.

## Definition Of Done

- Temos evidencia offline de quando Nash vence ou perde.
- Baselines simples ficam reproduziveis.
- Regressao de strategy selection vira teste automatizado.
- Relatorio aponta ajustes objetivos nos pesos.

## Anti-Escopo

- Nao alterar pesos em loop automatico ainda.
- Nao usar resultados sem fixture como verdade.
- Nao substituir testes existentes por relatorio.
