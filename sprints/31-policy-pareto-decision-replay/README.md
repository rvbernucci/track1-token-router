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

- [ ] Varrer `repair_threshold`.
- [ ] Varrer `remote_threshold`.
- [ ] Varrer `low_budget_deny_threshold`.
- [ ] Comparar exact-match proxy.
- [ ] Comparar packet tokens estimados.
- [ ] Comparar taxa de escalacao.
- [ ] Comparar budget violations.
- [ ] Gerar tabela Pareto.
- [ ] Marcar politicas dominadas.
- [ ] Sugerir perfil default.
- [ ] Criar `replay_decision.py --text`.
- [ ] Replay mostra guardrail/solver.
- [ ] Replay mostra risk signals.
- [ ] Replay mostra budget decision.
- [ ] Replay mostra policy decision.
- [ ] Replay mostra final validator.
- [ ] Replay mostra resposta final.
- [ ] Atualizar `submission/video-script.md` com exemplos reais.

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
