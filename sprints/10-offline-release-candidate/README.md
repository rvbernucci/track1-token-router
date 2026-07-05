# Sprint 10 - Offline Release Candidate

## Tipo

Nao depende de credito.

## Objetivo

Criar um release candidate que roda completamente sem creditos, mas esta pronto para receber endpoints reais assim que AMD/Fireworks forem liberados.

## Entregaveis

- Tag ou branch de release candidate.
- CI expandido com fake hybrid.
- Relatorio offline consolidado.
- README final de operacao sem credito.
- Plano de ativacao com credito.

## Checklist

- [x] Rodar suite completa.
- [x] Rodar offline eval arena.
- [x] Rodar comparacao de politicas.
- [x] Rodar fake provider chaos lab.
- [x] Rodar Docker no CI.
- [x] Gerar relatorio consolidado.
- [x] Atualizar `SUBMISSION.md`.
- [x] Criar `CREDIT_ACTIVATION.md`.
- [x] Criar tag `offline-rc`.
- [x] Confirmar que nenhum passo exige segredo real.

## Criterios de aceite

- [x] Qualquer pessoa consegue reproduzir a release candidate sem credito.
- [x] Quando os creditos chegarem, o trabalho vira configuracao de env vars e benchmark, nao refactor.
- [x] CI verde no commit/tag final.

## Evidencias

- `scripts/offline_release_check.sh`
- `reports/OFFLINE_RC_REPORT.md`
- `CREDIT_ACTIVATION.md`
- `.github/workflows/ci.yml`
- tag `offline-rc`

## Resultado

Release candidate offline pronta para operar sem credenciais reais e para receber creditos depois sem refactor estrutural.

## Riscos

- Release candidate divergir do ambiente real.
- Falta de dados reais esconder gargalos de latencia.

## Saida esperada

Um pacote competitivo offline, pronto para plugar creditos quando chegarem.
