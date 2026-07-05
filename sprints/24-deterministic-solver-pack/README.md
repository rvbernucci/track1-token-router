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
- Integracao opcional antes de M1 no modo competicao.

## Checklist

- [ ] Criar contrato `SolverResult`.
- [ ] Criar registry de solvers.
- [ ] Resolver soma, subtracao, multiplicacao e divisao inteira segura.
- [ ] Resolver comparacao numerica simples.
- [ ] Resolver contagem de caracteres.
- [ ] Resolver contagem de palavras.
- [ ] Resolver uppercase/lowercase/titlecase.
- [ ] Resolver trim/normalize whitespace.
- [ ] Resolver JSON compact quando payload for valido.
- [ ] Resolver JSON pretty quando payload for valido.
- [ ] Resolver extracao de primeiro/ultimo item de lista simples.
- [ ] Bloquear algebra, datas ambiguas e word problems.
- [ ] Adicionar testes de falso positivo.
- [ ] Adicionar testes de formato final.
- [ ] Medir rotas economizadas no battle drill.
- [ ] Documentar limites dos solvers.

## Criterios de aceite

- Solvers so respondem quando confidence for alta.
- Casos complexos passam para o runner normal.
- O solver pack reduz chamadas da cascata em tarefas mecanicas.
- O CI prova que nao estamos usando regex como raciocinio geral.

## Saida esperada

Um ganho real de eficiencia sem depender de modelo, credito ou heuristica fragil.

## Decisao

Cada solver deve ser pequeno, explicito e testado. Se a regra precisa de interpretacao semantica, ela nao pertence ao solver deterministico.

