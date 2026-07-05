# Sprint 33 - Bad Local Model Chaos Lab

## Tipo

Nao depende de credito.

## Objetivo

Simular modelos locais ruins, instaveis ou superconfiantes para testar se M2A, policy engine, final validator e budget conseguem impedir respostas "bonitas e erradas" de passarem.

## Por que importa

A arquitetura so vence se o verificador local nao aprovar candidato ruim. Sem creditos, ainda podemos simular falhas de modelo local com fake provider e fixtures controladas.

## Tese

O maior risco nao e o modelo local errar. O maior risco e o sistema confiar no erro.

## Entregaveis

- Novos perfis no fake provider para respostas ruins.
- `fixtures/chaos/bad-local-model/*.jsonl`.
- `scripts/bad_local_model_drill.py`.
- `reports/generated/bad-local-model-report.md`.
- Testes de overconfidence, format drift, hallucination e empty answer.
- Integracao opcional ao battle drill como `bad_local_model_ready`.

## Checklist

- [x] Criar perfil `hallucination_confident`.
- [x] Criar perfil `format_drift`.
- [x] Criar perfil `empty_or_refusal`.
- [x] Criar perfil `verbose_when_strict`.
- [x] Criar perfil `wrong_math_plausible`.
- [x] Criar fixture de tarefas que parecem faceis mas exigem validacao.
- [x] Medir taxa de aprovacao indevida.
- [x] Medir taxa de reparo local.
- [x] Medir taxa de remote audit dry-run.
- [x] Falhar em `--check` quando aprovacao indevida passar limite.
- [x] Confirmar que final validator repara formatos estritos simples.
- [x] Confirmar que perguntas atuais/riscadas escalam.
- [x] Adicionar testes automatizados para cada perfil ruim.

## Criterios de aceite

- O drill roda sem modelo real.
- Candidatos ruins sao barrados ou reparados de forma observavel.
- O relatorio mostra falsos aprovados, reparos e escalacoes.
- O CI protege contra regressao de M2A/policy/final validator.

## Metricas

- False approval rate.
- Repair rate.
- Remote audit dry-run rate.
- Strict format failure rate.
- Token exposure adicional por caos.

## Comandos esperados

```bash
python3 scripts/bad_local_model_drill.py --check --report reports/generated/bad-local-model-report.md
python3 -m unittest tests.test_bad_local_model_chaos
```

## Riscos

- Criar caos artificial demais e otimizar para um monstro inventado.
- Transformar M2A em bloqueador excessivo e queimar tokens remotos.
- Esquecer que o objetivo e calibrar confianca, nao punir todo candidato local.

## Decisao

O fake provider deve simular classes de falha, nao modelos especificos. O objetivo e robustez de orquestracao.

## Definition of Done

- Perfis ruins existem.
- Drill mede aprovacoes indevidas.
- Gate de regressao existe.
- Battle/readiness sabe apontar risco de modelo local ruim.
