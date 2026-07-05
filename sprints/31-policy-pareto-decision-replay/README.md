# Sprint 31 - Policy Pareto And Decision Replay

## Tipo

Nao depende de credito.

## Objetivo

Criar ferramentas offline para explorar a fronteira de Pareto das politicas de roteamento e gerar replays legiveis de decisoes individuais.

## Por que importa

O projeto precisa justificar por que a politica default e boa. Alem disso, a demo e o pitch ficam muito mais fortes quando conseguimos mostrar uma decisao real passo a passo.

## Tese

O melhor argumento tecnico nao e "temos uma cascata". E "esta decisao economizou tokens sem sacrificar formato, budget ou confianca".

## Entregaveis

- `scripts/optimize_policy.py`.
- `scripts/replay_decision.py`.
- `reports/generated/policy-pareto.md`.
- `reports/generated/decision-replay.md`.
- Perfil default recomendado e justificativa.
- Atualizacao do video script com exemplos reais.
- Testes de replay e optimizer.

## Checklist

- [x] Varrer `repair_threshold`.
- [x] Varrer `remote_threshold`.
- [x] Varrer `low_budget_deny_threshold`.
- [x] Comparar exact-match proxy.
- [x] Comparar packet tokens estimados.
- [x] Comparar taxa de escalacao.
- [x] Comparar budget violations.
- [x] Gerar tabela Pareto.
- [x] Marcar politicas dominadas.
- [x] Sugerir perfil default.
- [x] Criar `replay_decision.py --text`.
- [x] Replay mostra guardrail/solver.
- [x] Replay mostra risk signals.
- [x] Replay mostra budget decision.
- [x] Replay mostra policy decision.
- [x] Replay mostra final validator.
- [x] Replay mostra resposta final.
- [x] Atualizar `submission/video-script.md` com exemplos reais.

## Criterios de aceite

- `optimize_policy.py` roda sem modelo real.
- Relatorio Pareto diferencia politicas dominadas e candidatas.
- `replay_decision.py` gera Markdown util para demo.
- O perfil default continua documentado como decisao, nao chute.
- O video script ganha pelo menos dois exemplos concretos.

## Metricas

- Exact match proxy por perfil.
- Remote packet tokens por perfil.
- Escalation rate por perfil.
- Budget violations por perfil.
- Numero de politicas dominadas.

## Comandos esperados

```bash
python3 scripts/optimize_policy.py --report reports/generated/policy-pareto.md
python3 scripts/replay_decision.py --text "What is 6 * 7? Return only the number." --report reports/generated/decision-replay.md
```

## Riscos

- Superotimizar para o dataset offline.
- Confundir proxy de exact match com scoring oficial.
- Escolher perfil agressivo demais por economia aparente.

## Decisao

O optimizer informa, mas nao substitui julgamento humano. A politica final deve considerar accuracy, token exposure, latencia e robustez contra formato desconhecido.

## Definition of Done

- Pareto report existe.
- Decision replay existe.
- Perfil default tem justificativa.
- Video script referencia replays reais.
- Battle drill continua sendo a porteira principal.

## Evidencias

- `scripts/optimize_policy.py --check` varre thresholds e gera `reports/generated/policy-pareto.md`.
- Optimizer recomenda `repair=3;remote=5;low_budget=0.05`, preservando o default atual quando ele empata na melhor superficie Pareto.
- `scripts/replay_decision.py --text "What is 6 * 7? Return only the number."` gera replay Markdown com solver, risk signals, budget, policy e final validator.
- `tests/test_policy_optimizer_replay.py` cobre recomendacao Pareto e replay de decisao.
- `submission/video-script.md` referencia replays concretos para solver zero-token e pergunta de conhecimento atual.
- `scripts/offline_release_check.sh` executa optimizer e replay antes do battle drill.
