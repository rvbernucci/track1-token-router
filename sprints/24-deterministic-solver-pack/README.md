# Sprint 24 - Deterministic Solver Pack

## Tipo

Nao depende de credito.

## Objetivo

Expandir os guardrails para um pacote de solvers deterministicos seguros, focados em tarefas mecanicas que nao precisam de LLM local nem Fireworks.

## Por que importa

Se codigo resolve com certeza, usar LLM e desperdicio de latencia e risco. O solver pack aumenta accuracy em tarefas mecanicas e reduz pressao sobre a cascata.

## Entregaveis

- Modulo `router/orchestration/solvers.py`.
- Registro de solvers com nome, confidence e reason.
- Solvers seguros para matematica e transformacao simples.
- Testes de falso positivo.
- Metricas de economia no battle drill.
- Registro reutilizado como engine candidato quando `sub_intent` e a regressao indicarem alto `deterministic_fit`.

## Checklist

- [x] Criar contrato `SolverResult`.
- [x] Criar registry de solvers.
- [x] Resolver soma, subtracao, multiplicacao e divisao inteira segura.
- [x] Resolver comparacao numerica simples.
- [x] Resolver contagem de caracteres.
- [x] Resolver contagem de palavras.
- [x] Resolver uppercase/lowercase/titlecase.
- [x] Resolver trim/normalize whitespace.
- [x] Resolver JSON compact quando payload for valido.
- [x] Resolver JSON pretty quando payload for valido.
- [x] Resolver extracao de primeiro/ultimo item de lista simples.
- [x] Bloquear algebra, datas ambiguas e word problems.
- [x] Adicionar testes de falso positivo.
- [x] Adicionar testes de formato final.
- [x] Medir rotas economizadas no battle drill.
- [x] Documentar limites dos solvers.

## Criterios de aceite

- Solvers so respondem quando confidence for alta.
- Casos complexos passam para o runner normal.
- O solver pack reduz chamadas da cascata em tarefas mecanicas.
- O CI prova que nao estamos usando regex como raciocinio geral.

## Saida esperada

Um ganho real de eficiencia sem depender de modelo, credito ou heuristica fragil.

## Decisao

Cada solver deve ser pequeno, explicito e testado. Se a regra precisa de interpretacao semantica, ela nao pertence ao solver deterministico.

## Evidencia de fechamento

- `python3 -m unittest tests.test_solvers tests.test_competition_mode tests.test_state_machine tests.test_battle_drill`: 25 testes focados passando.
- `ROUTER_MODE=competition COMPETITION_DRY_RUN=1 python3 -m router ask "What is 6 * 7? Return only the number." --json`: rota `solver_arithmetic`, resposta `42`, zero tokens remotos.
- `python3 scripts/battle_drill.py`: `solver_pack_ready=true`.
- Limites documentados em `docs/DETERMINISTIC_SOLVERS.md`.
