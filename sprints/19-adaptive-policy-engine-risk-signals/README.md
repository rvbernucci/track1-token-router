# Sprint 19 - Adaptive Policy Engine & Risk Signals

## Tipo

Nao depende de credito.

## Objetivo

Trocar politicas fixas por uma policy engine baseada em sinais: risco de formato, risco matematico, incerteza local, instabilidade factual, historico de parse e budget restante.

## Por que importa

`aggressive`, `balanced` e `conservative` sao bons modos de laboratorio. Para competir, a politica precisa reagir a cada task e ao estado do run.

## Entregaveis

- Modulo `router/orchestration/risk_signals.py`.
- Modulo `router/orchestration/policy_engine.py`.
- Contrato `RiskSignalSet`.
- Contrato `PolicyDecision`.
- Thresholds configuraveis.
- Ablation de thresholds.
- Testes com dataset offline.

## Checklist

- [ ] Extrair sinal de formato estrito.
- [ ] Extrair sinal de matematica simples vs complexa.
- [ ] Extrair sinal de conhecimento instavel.
- [ ] Extrair sinal de prompt injection.
- [ ] Extrair sinal de resposta vazia/curta demais.
- [ ] Extrair sinal de resposta longa demais.
- [ ] Usar confidence do M2A quando existir.
- [ ] Usar budget restante.
- [ ] Usar historico de parse failures.
- [ ] Gerar `PolicyDecision` com `approve`, `repair`, `remote_audit` ou `deny_remote`.
- [ ] Criar ablation de thresholds offline.
- [ ] Adicionar testes adversariais.

## Criterios de aceite

- A decisao de escalar tem razoes estruturadas.
- Thresholds podem ser alterados sem mexer em prompt.
- A policy engine melhora ou iguala o score offline em relacao ao baseline.
- Decisoes arriscadas ficam explicitas no trace.

## Saida esperada

Uma camada de decisao que joga o jogo, nao apenas segue um modo fixo.

