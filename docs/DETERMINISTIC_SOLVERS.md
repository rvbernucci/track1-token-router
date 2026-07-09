# Deterministic Solver Pack

## Papel

O solver pack resolve tarefas mecanicas antes do M1 no `ROUTER_MODE=competition`.

Ele existe para economizar latencia e reduzir risco quando a resposta pode ser calculada ou transformada com confianca alta por codigo.

## Solvers ativos

| solver | cobre | limite de seguranca |
|---|---|---|
| `arithmetic` | soma, subtracao, multiplicacao e divisao inteira exata | apenas expressoes inteiras de uma operacao |
| `percent_fee_math` | desconto percentual unico seguido de fee fixa | exige formula textual `cost/price -> percent discount -> fee added` |
| `proportional_rate` | taxa linear de unidades identicas | exige frase com unidades identicas, producao total e novo numero de unidades |
| `numeric_compare` | maior/menor entre dois numeros | exige exatamente dois numeros e palavra-chave de comparacao |
| `sentiment_lexicon` | sentimento explicito `positive/neutral/negative` | exige prompt de sentimento, marcador `Text:` e margem lexical clara |
| `entity_extract` | JSON minificado para padroes NER mecanicos | apenas pagamento datado, fundacao pessoa/org/cidade e contato email/url/phone |
| `logic_ordering` | endpoint de ordenacao transitiva simples | exige relacoes comparativas nominais e endpoint unico |
| `modus_ponens` | inferencia `if A then B; A; is B?` | responde apenas `yes` quando antecedente e consequente normalizados batem exatamente |
| `python_code_debug` | correcoes Python de bugs triviais conhecidos | apenas assinaturas e sintomas exatos testados por `python_function_cases` |
| `python_code_generation` | funcoes Python pequenas de utilidade comum | apenas templates sem `import`, executaveis pelo validador seguro |
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
- Sentimento misto ou sem margem lexical fica fora.
- NER generico fica fora; o solver so entra em padroes estruturais comprovaveis.
- Logica com contrapositiva, afirmacao do consequente ou grafos desconectados fica fora.
- Programacao generica fica fora; os templates Python so entram quando assinatura, verbo e criterio batem exatamente.
- Templates Python nao usam `import`, `open`, `eval`, classes ou estado global, para ficarem compativeis com o validador seguro do microbench.

## Track 1 payoff

O Track 1 inclui factual Q&A, math reasoning, sentiment, summarization, NER, code debugging, logic puzzles e code generation.

Este pack nao tenta substituir os modelos nessas oito categorias. Ele remove do caminho remoto apenas os subcasos em que codigo e mais confiavel que LLM:

- math reasoning mecanico com formula unica;
- sentiment obvio com vocabulario explicitamente polarizado;
- NER estrutural em frases regulares;
- logic puzzles de uma inferencia ou uma cadeia transitiva curta;
- code debugging/code generation em templates Python pequenos e executaveis;
- transformacoes de formato e contagem.

O ganho esperado e reduzir chamadas Fireworks sem derrubar o accuracy gate. Quando o padrao nao e claro, `solve_deterministic` retorna `None` e a cascata/model router continua normalmente.

## Gate de regressao

Antes de mexer em qualquer solver, rode:

```bash
python3 scripts/track1_deterministic_coverage.py --check
```

Esse gate roda os microbenches locais de Track 1 com `CompetitionRunner` em dry-run, valida somente rotas `solver_*` e `guardrail_*` contra os validadores do dataset e falha se:

- qualquer output deterministico validavel estiver incorreto;
- a cobertura deterministica cair abaixo do piso configurado.

O mesmo gate tambem roda dentro de `scripts/offline_release_check.sh`.

## Regra operacional

Se a regra precisa interpretar contexto amplo, ela nao e solver deterministico.

O caminho correto nesses casos e deixar a cascata local ou serverless decidir.
