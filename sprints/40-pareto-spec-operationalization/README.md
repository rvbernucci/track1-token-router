# Sprint 40 - Pareto Spec Operationalization

## Tipo

Nao depende de credito.

## Objetivo

Transformar Pareto e teoria dos jogos em especificacoes executaveis: todo comportamento central do roteador precisa ter spec, plano, tasks, testes e criterio de aceite.

## Tese

Uma estrategia so vira vantagem competitiva quando ela e rastreavel. Se nao conseguimos explicar por spec por que um modelo foi chamado, nao conseguimos calibrar nem defender a decisao.

## Entregaveis

- `specs/000-constitution/constitution.md`.
- `specs/001-fireworks-pareto-router/spec.md`.
- `specs/001-fireworks-pareto-router/plan.md`.
- `specs/001-fireworks-pareto-router/tasks.md`.
- `specs/002-game-theory-selection/spec.md`.
- `specs/002-game-theory-selection/plan.md`.
- `specs/002-game-theory-selection/tasks.md`.
- `docs/SPEC_CONVERGENCE_CHECKLIST.md`.

## Checklist

- [ ] Criar constituicao operacional com principios nao negociaveis.
- [ ] Especificar requisitos do Pareto Router.
- [ ] Especificar requisitos da matriz de correlacao e Nash welfare.
- [ ] Vincular cada requisito a pelo menos um teste existente ou planejado.
- [ ] Documentar criterios de aceite por dominio de tarefa.
- [ ] Criar checklist de convergencia spec -> code -> tests -> docs.
- [ ] Atualizar `docs/TEST_MATRIX.md` com referencias a specs.
- [ ] Rodar `python3 -m unittest tests.test_fireworks_model_router`.
- [ ] Rodar `python3 scripts/secret_scan.py`.

## Metricas

- requisitos com teste vinculado;
- decisoes de roteamento com criterio de aceite;
- specs sem `[NEEDS CLARIFICATION]`;
- divergencias encontradas entre docs e codigo.

## Definition Of Done

- As duas features centrais tem `spec.md`, `plan.md` e `tasks.md`.
- Toda regra critica do roteador aparece em uma spec.
- A matriz de teste aponta para as specs.
- Checks locais passam.

## Anti-Escopo

- Nao instalar `specify-cli` ainda.
- Nao mudar heuristica sem teste.
- Nao criar especificacao generica sem criterio de aceite.
