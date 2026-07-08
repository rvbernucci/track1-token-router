# Sprint 38 - Fireworks Model Router Cost Optimizer

## Tipo

Nao depende de credito.

## Objetivo

Adaptar o projeto ao esclarecimento oficial do Track 1: o jogo principal e escolher, em tempo real, o modelo Fireworks mais barato que ainda deve passar o accuracy gate.

Local models continuam uteis para desenvolvimento, avaliacao offline e calibracao, mas o caminho final precisa rotear chamadas Fireworks por `FIREWORKS_BASE_URL` usando apenas modelos de `ALLOWED_MODELS`.

## Tese

O vencedor nao e quem evita Fireworks a qualquer custo. O vencedor e quem escolhe o menor modelo Fireworks suficiente para cada task.

## Entregaveis

- Roteador de modelos Fireworks baseado em `ALLOWED_MODELS`.
- Ranking heuristico de custo/capacidade por nome/tamanho do modelo.
- Selecionador por tipo de task: cheap, medium, strong.
- Metadata com `fireworks_model_selection`.
- Testes para ranking e selecao.
- Integracao com `ROUTER_MODE=fireworks`.

## Checklist

- [x] Criar `router/orchestration/fireworks_model_router.py`.
- [x] Implementar ranking por tamanho/keyword de modelo.
- [x] Implementar selecao cheap/medium/strong.
- [x] Usar modelo selecionado no payload OpenAI-compatible.
- [x] Registrar selecao em metadata.
- [x] Preservar deterministic solvers antes de Fireworks.
- [x] Adicionar testes de ranking.
- [x] Adicionar testes de selecao por categoria.
- [x] Adicionar teste garantindo que o payload usa o modelo selecionado.
- [ ] Calibrar contra `ALLOWED_MODELS` real quando sair.
- [ ] Adicionar tabela de custo real se a organizacao publicar precos/modelos.
- [ ] Medir accuracy/token por tier quando houver creditos.

## Categorias oficiais e tier inicial

- Sentiment classification: `cheap`.
- Strict formatting/simple extraction: `cheap`.
- Text summarisation: `medium`.
- Named entity recognition: `medium`.
- Factual knowledge: `medium` ou `strong` se atual/especifico.
- Mathematical reasoning: `strong` quando multi-step.
- Logical / deductive reasoning: `strong`.
- Code debugging/generation: `strong`.

## Riscos

- Nome do modelo nao refletir custo real.
- Modelo barato passar token baixo mas falhar accuracy gate.
- Modelo forte ser usado demais e matar ranking por tokens.
- O prompt unico nao estar otimizado por tier.

## Definition of Done

- O caminho oficial nao escolhe sempre o primeiro modelo.
- A escolha do modelo e auditavel por task.
- A estrategia pode ser recalibrada sem trocar o contrato Docker.
