# Sprint 39 - Spec-Driven Governance

## Tipo

Nao depende de credito.

## Objetivo

Adotar o melhor do `github/spec-kit` sem instalar ou acoplar a ferramenta ainda: especificacao como fonte da verdade, plano tecnico rastreavel, tarefas derivadas e convergencia entre docs, testes e codigo.

## Tese

O Track 1 e um problema de decisao sob restricoes. Se a especificacao nao governa o codigo, cada heuristica de roteamento vira opiniao. Se a especificacao governa, cada mudanca precisa provar sua relacao com scoring, token budget e accuracy.

## Entregaveis

- Documento de adocao do Spec Kit.
- Constituicao operacional do projeto.
- Estrutura inicial `specs/`.
- Primeira spec retroativa para o Fireworks Pareto Router.
- Primeira spec retroativa para Game Theory Model Selection.
- Checklist de convergencia spec -> plan -> tasks -> tests.
- Decisao documentada sobre instalar ou nao `specify-cli`.

## Checklist

- [x] Mapear `github/spec-kit` e conceitos relevantes.
- [x] Criar `docs/SPEC_KIT_ADOPTION.md`.
- [ ] Criar `specs/000-constitution/constitution.md`.
- [ ] Criar `specs/001-fireworks-pareto-router/spec.md`.
- [ ] Criar `specs/001-fireworks-pareto-router/plan.md`.
- [ ] Criar `specs/001-fireworks-pareto-router/tasks.md`.
- [ ] Criar `specs/002-game-theory-selection/spec.md`.
- [ ] Criar `specs/002-game-theory-selection/plan.md`.
- [ ] Criar `specs/002-game-theory-selection/tasks.md`.
- [ ] Adicionar checklist de convergencia em `docs/SPEC_CONVERGENCE_CHECKLIST.md`.
- [ ] Decidir se vale instalar `specify-cli` apos revisar dry-run/arquivos gerados.

## Constituicao Inicial

Principios nao negociaveis:

- O scoring oficial manda.
- Accuracy abaixo do gate invalida economia de token.
- Fireworks tokens sao recurso escasso.
- Toda decisao de modelo precisa ser auditavel.
- `ALLOWED_MODELS` governa o caminho oficial.
- Embedding e reranker nao produzem resposta final.
- A rota offline nao pode depender de credito.
- Testes devem cobrir toda regra competitiva.
- Logs nunca podem expor segredo ou payload sensivel desnecessario.
- O projeto continua CLI-first e Docker-ready.

## Definition Of Done

- Existe uma constituicao do projeto.
- Pelo menos duas features centrais tem spec, plan e tasks.
- O roteador consegue ser explicado a partir da especificacao, nao apenas do codigo.
- `scripts/offline_release_check.sh` continua passando.
- A decisao sobre instalar ou nao Spec Kit fica documentada.

## Anti-Escopo

- Nao instalar `specify-cli` diretamente no repo sem decisao explicita.
- Nao sobrescrever estrutura existente com templates automaticos.
- Nao criar burocracia que atrase entrega.
- Nao transformar specs em docs mortos sem testes vinculados.
