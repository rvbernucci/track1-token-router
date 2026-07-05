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

- [ ] Rodar suite completa.
- [ ] Rodar offline eval arena.
- [ ] Rodar comparacao de politicas.
- [ ] Rodar fake provider chaos lab.
- [ ] Rodar Docker no CI.
- [ ] Gerar relatorio consolidado.
- [ ] Atualizar `SUBMISSION.md`.
- [ ] Criar `CREDIT_ACTIVATION.md`.
- [ ] Criar tag `offline-rc`.
- [ ] Confirmar que nenhum passo exige segredo real.

## Criterios de aceite

- Qualquer pessoa consegue reproduzir a release candidate sem credito.
- Quando os creditos chegarem, o trabalho vira configuracao de env vars e benchmark, nao refactor.
- CI verde no commit/tag final.

## Riscos

- Release candidate divergir do ambiente real.
- Falta de dados reais esconder gargalos de latencia.

## Saida esperada

Um pacote competitivo offline, pronto para plugar creditos quando chegarem.

