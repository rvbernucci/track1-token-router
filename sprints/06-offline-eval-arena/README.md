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

- [x] Criar `evals/offline/tasks.jsonl`.
- [x] Criar `evals/offline/expected.jsonl`.
- [x] Adicionar campo `metadata.category`.
- [x] Adicionar campo `metadata.difficulty`.
- [x] Adicionar campo `metadata.expected_route`.
- [x] Criar tarefas triviais que devem sair localmente.
- [x] Criar tarefas de formato estrito.
- [x] Criar tarefas matematicas multi-etapa.
- [x] Criar tarefas adversariais de prompt injection.
- [x] Criar tarefas de conhecimento possivelmente desatualizado.
- [x] Criar relatorio por categoria.
- [x] Garantir que o dataset nao usa dados sensiveis.

## Criterios de aceite

- [x] `python3 -m router eval --jsonl evals/offline/tasks.jsonl --expected evals/offline/expected.jsonl` roda sem provedores reais.
- [x] O relatorio mostra rotas, exact match, escalations e tokens remotos simulados.
- [x] O dataset tem cobertura minima por categoria.
- [x] O README explica como adicionar novas tarefas.

## Evidencias

- `python3 scripts/generate_offline_eval.py`
- `python3 scripts/generate_offline_eval.py --check`
- `wc -l evals/offline/tasks.jsonl evals/offline/expected.jsonl`
- `python3 -m router eval --jsonl evals/offline/tasks.jsonl --expected evals/offline/expected.jsonl --report reports/generated/offline-report.md`
- `python3 -m unittest discover -s tests`

## Resultado

- 160 tarefas offline.
- 8 categorias com 20 tarefas cada.
- Metadados por tarefa: `category`, `difficulty`, `expected_route`, `risk`.
- Relatorio do `router eval` inclui `categories`, `difficulties` e `expected_route`.

## Riscos

- Dataset artificial demais.
- Exact match punir respostas semanticamente corretas.
- Medir so accuracy e esquecer custo/latencia.

## Saida esperada

Uma arena offline que permite continuar calibrando sem depender de creditos.
