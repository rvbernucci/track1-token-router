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

- [x] Extrair sinal de formato estrito.
- [x] Extrair sinal de matematica simples vs complexa.
- [x] Extrair sinal de conhecimento instavel.
- [x] Extrair sinal de prompt injection.
- [x] Extrair sinal de resposta vazia/curta demais.
- [x] Extrair sinal de resposta longa demais.
- [x] Usar confidence do M2A quando existir.
- [x] Usar budget restante.
- [x] Usar historico de parse failures.
- [x] Gerar `PolicyDecision` com `approve`, `repair`, `remote_audit` ou `deny_remote`.
- [x] Criar ablation de thresholds offline.
- [x] Adicionar testes adversariais.

## Criterios de aceite

- A decisao de escalar tem razoes estruturadas.
- Thresholds podem ser alterados sem mexer em prompt.
- A policy engine melhora ou iguala o score offline em relacao ao baseline.
- Decisoes arriscadas ficam explicitas no trace.

## Saida esperada

Uma camada de decisao que joga o jogo, nao apenas segue um modo fixo.

## Evidencia local

```bash
python3 -m unittest tests.test_policy_engine
python3 scripts/policy_ablation.py
scripts/offline_release_check.sh
```

## Decisao

A policy engine ainda nao substitui a cascata em runtime por padrao. Ela cria uma decisao estruturada e comparavel offline. Isso reduz risco: primeiro medimos thresholds e sinais; depois integramos no caminho quente quando o battle drill provar vantagem.
