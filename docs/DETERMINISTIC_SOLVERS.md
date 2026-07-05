# Deterministic Solver Pack

## Papel

O solver pack resolve tarefas mecanicas antes do M1 no `ROUTER_MODE=competition`.

Ele existe para economizar latencia e reduzir risco quando a resposta pode ser calculada ou transformada com confianca alta por codigo.

## Solvers ativos

| solver | cobre | limite de seguranca |
|---|---|---|
| `arithmetic` | soma, subtracao, multiplicacao e divisao inteira exata | apenas expressoes inteiras de uma operacao |
| `numeric_compare` | maior/menor entre dois numeros | exige exatamente dois numeros e palavra-chave de comparacao |
| `char_count` | contagem de caracteres | exige string entre aspas |
| `word_count` | contagem de palavras | exige string entre aspas |
| `case_transform` | uppercase, lowercase, titlecase | exige string entre aspas |
| `whitespace` | trim e normalizacao de whitespace | exige string entre aspas |
| `json_transform` | JSON compact e pretty | exige payload JSON valido |
| `list_item` | primeiro/ultimo item | apenas lista JSON simples ou lista separada por virgulas |

## Bloqueios deliberados

- Algebra, equacoes, derivadas e integrais ficam fora.
- Datas relativas ou ambiguas ficam fora.
- Word problems ficam fora, mesmo quando parecem calculaveis.
- Divisao nao inteira e divisao por zero ficam fora.
- Tarefas que pedem ordenacao ficam fora, mesmo se tambem pedirem primeiro/ultimo item.
- Strings sem aspas ficam fora em solvers de contagem e transformacao.

## Regra operacional

Se a regra precisa interpretar contexto amplo, ela nao e solver deterministico.

O caminho correto nesses casos e deixar a cascata local ou serverless decidir.
