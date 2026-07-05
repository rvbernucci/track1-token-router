# Sprint 06 - Offline Evaluation Arena

## Tipo

Nao depende de credito.

## Objetivo

Criar uma arena de avaliacao offline forte o suficiente para calibrar o roteador antes de ter acesso real a AMD Developer Cloud ou Fireworks.

Sem credito, o ativo mais importante e dataset. Ele nos diz onde a cascata erra, onde escala demais e onde gasta token remoto simulado sem necessidade.

## Entregaveis

- Dataset offline com 100-300 tarefas.
- Categorias: facil, media, dificil, formato, matematica, instrucao, adversarial, conhecimento instavel.
- Expected answers quando houver resposta objetiva.
- Metadados de dificuldade e risco.
- Relatorio por categoria.
- Comando de geracao/validacao do dataset.

## Checklist

- [ ] Criar `evals/offline/tasks.jsonl`.
- [ ] Criar `evals/offline/expected.jsonl`.
- [ ] Adicionar campo `metadata.category`.
- [ ] Adicionar campo `metadata.difficulty`.
- [ ] Adicionar campo `metadata.expected_route`.
- [ ] Criar tarefas triviais que devem sair localmente.
- [ ] Criar tarefas de formato estrito.
- [ ] Criar tarefas matematicas multi-etapa.
- [ ] Criar tarefas adversariais de prompt injection.
- [ ] Criar tarefas de conhecimento possivelmente desatualizado.
- [ ] Criar relatorio por categoria.
- [ ] Garantir que o dataset nao usa dados sensiveis.

## Criterios de aceite

- `python3 -m router eval --jsonl evals/offline/tasks.jsonl --expected evals/offline/expected.jsonl` roda sem provedores reais.
- O relatorio mostra rotas, exact match, escalations e tokens remotos simulados.
- O dataset tem cobertura minima por categoria.
- O README explica como adicionar novas tarefas.

## Riscos

- Dataset artificial demais.
- Exact match punir respostas semanticamente corretas.
- Medir so accuracy e esquecer custo/latencia.

## Saida esperada

Uma arena offline que permite continuar calibrando sem depender de creditos.

