# Mechanical Validator And Solver Pack

## Championship False-Positive Audit

On the frozen 571-task validation/test corpus, the pre-hardening registry accepted 14 tasks. Independent Claude Sonnet 5 and Gemini judges agreed that 13 were incorrect and one was correct. Incidental `max`, `lowercase`, character-count and JSON-schema language had triggered solvers outside their complete contracts.

The championship revision replaced those keyword checks with full task-contract matches and explicit code/JSON guards. Replaying the same 571 tasks produced zero acceptances and 571 safe refusals. Deterministic execution remains available only for the separately tested exact-template pack; broad corpus prompts fall through to E2B or Fireworks.

## Papel

O solver pack resolve tarefas mecanicas antes do caminho de modelo no `ROUTER_MODE=competition`.

Ele existe para economizar latencia e reduzir risco quando a resposta pode ser calculada ou transformada com confianca alta por codigo.

Ele nao e o nucleo de inteligencia do Track 1. O nucleo e o agente general-purpose que interpreta a tarefa, escolhe o menor modelo suficiente em `ALLOWED_MODELS` e preserva accuracy. Este pack e a camada de seguranca: schema, formato, calculos estreitos e verificacoes mecanicas.

## Solvers ativos

| solver | cobre | limite de seguranca |
|---|---|---|
| `arithmetic` | soma, subtracao, multiplicacao, divisao inteira exata e media aritmetica explicita | apenas expressoes inteiras curtas ou frase `scores -> arithmetic mean` |
| `percent_fee_math` | desconto percentual unico seguido de fee fixa; aumento percentual repetido explicito | exige formula textual comprovavel e percentuais limitados |
| `proportional_rate` | taxa linear de unidades identicas | exige frase com unidades identicas, producao total e novo numero de unidades |
| `numeric_compare` | maior/menor entre dois numeros; JSON min/max; JSON sum/product | exige lista numerica curta ou exatamente dois numeros e palavra-chave de comparacao |
| `stable_factual_qa` | fatos estaveis de altissima confianca | apenas whitelist exact-prompt com `return only`; bloqueia `today/latest/current/now/as of` |
| `sentiment_lexicon` | sentimento explicito `positive/neutral/negative` | exige prompt de sentimento, marcador `Text:` e margem lexical clara ou frase factual neutra |
| `constrained_summary` | resumos curtos com limite de palavras e termos obrigatorios/inferiveis | apenas templates que obedecem mecanicamente `at most N words` |
| `entity_extract` | JSON minificado e campos simples para padroes NER mecanicos | apenas pagamento datado, invoice/date/amount, fundacao pessoa/org/cidade, compra/pedido cliente/item/cidade, key/value pairs, nomes simples, title e invoice code |
| `logic_ordering` | endpoint de ordenacao transitiva simples e silogismos quantificados estreitos | exige relacoes comparativas nominais, endpoint unico ou padrao `all/no` / `all/some` comprovavel |
| `modus_ponens` | inferencia `if A then B; A; is B?` | responde apenas `yes` quando antecedente e consequente normalizados batem exatamente |
| `python_code_debug` | correcoes Python de bugs triviais conhecidos | apenas assinaturas e sintomas exatos testados por `python_function_cases` |
| `python_code_generation` | funcoes Python pequenas de utilidade comum | apenas templates sem `import`, executaveis pelo validador seguro |
| `char_count` | contagem de caracteres | exige string entre aspas |
| `word_count` | contagem de palavras | exige string entre aspas |
| `case_transform` | uppercase, lowercase, titlecase | exige string entre aspas ou marcador mecanico `version of this text:` |
| `whitespace` | trim e normalizacao de whitespace | exige string entre aspas |
| `json_transform` | JSON compact e pretty | exige payload JSON valido |
| `list_item` | primeiro/ultimo item e ordinais pequenos | apenas lista JSON simples ou lista separada por virgulas |

## Bloqueios deliberados

- Algebra, equacoes, derivadas e integrais ficam fora.
- Datas relativas ou ambiguas ficam fora.
- Word problems amplos ficam fora, mesmo quando parecem calculaveis.
- Divisao nao inteira e divisao por zero ficam fora.
- Tarefas que pedem ordenacao ficam fora, mesmo se tambem pedirem primeiro/ultimo item.
- Strings sem aspas ficam fora em solvers de contagem; transformacao sem aspas so entra com marcador `this text:`.
- Sentimento misto ou sem margem lexical fica fora.
- NER generico fica fora; o solver so entra em padroes estruturais comprovaveis.
- Factual QA generico fica fora; so fatos estaveis explicitamente whitelisted entram.
- Summarization aberta fica fora; so resumos curtos com restricao mecanicamente validavel entram.
- Logica com contrapositiva, afirmacao do consequente ou grafos desconectados fica fora.
- Programacao generica fica fora; os templates Python so entram quando assinatura, verbo e criterio batem exatamente.
- Templates Python nao usam `import`, `open`, `eval`, classes ou estado global, para ficarem compativeis com o validador seguro do microbench.

## Track 1 payoff

O Track 1 inclui factual Q&A, math reasoning, sentiment, summarization, NER, code debugging, logic puzzles e code generation.

Este pack nao tenta substituir os modelos nessas oito categorias. Ele remove do caminho remoto apenas os subcasos em que codigo e mais confiavel que LLM:

- math reasoning mecanico com formula unica;
- factual QA estavel em whitelist estreita;
- sentiment obvio com vocabulario explicitamente polarizado;
- summarization curta com limite de palavras e termos obrigatorios;
- NER estrutural em frases regulares;
- logic puzzles de uma inferencia ou uma cadeia transitiva curta;
- code debugging/code generation em templates Python pequenos e executaveis;
- transformacoes de formato e contagem.

O ganho esperado e reduzir chamadas Fireworks sem derrubar o accuracy gate. Quando o padrao nao e claro, `solve_deterministic` retorna `None` e o model router continua normalmente.

## Gate de regressao

Antes de mexer em qualquer solver, rode:

```bash
python3 scripts/track1_deterministic_coverage.py --check
```

Esse gate roda os microbenches locais de Track 1 com `CompetitionRunner` em dry-run, valida somente rotas `solver_*` e `guardrail_*` contra os validadores do dataset e falha se:

- qualquer output deterministico validavel estiver incorreto;
- a cobertura deterministica cair abaixo do piso configurado.

O mesmo gate tambem roda dentro de `scripts/offline_release_check.sh`.

Resultado atual nos datasets locais de campeonato, hidden-variant, adversarial-hidden, frontier e structure-heldout: `111/111` tarefas resolvidas por rota deterministica ou guardrail, com `100%` de validade nos outputs deterministicos.

O dataset `evals/fireworks-pareto/adversarial-hidden-microbench.jsonl` foi adicionado como gate anti-overfitting. Ele cobre variantes mecanicas de factual QA, matematica, sentimento, summarization, NER, logic puzzles, code debugging, code generation e formatting. O objetivo nao e simular conhecimento aberto; e provar que subcasos estritamente verificaveis continuam saindo com zero token remoto mesmo quando a frase muda.

Um runtime eval complementar com endpoint Fireworks propositalmente inalcançavel validou `108/108` tarefas unicas deduplicadas, `fireworks_tasks=0`, `remote_tokens.total=0` e custo `$0.00` em `reports/generated/fireworks-runtime-zero-token-111-report.md`.

O relatorio gerado tambem lista rotas nao deterministicas restantes. Em 2026-07-09, o gate ampliado nao possui rotas nao deterministicas nos seis microbenches locais, mas isso nao significa que todo factual QA ou summarization deve virar codigo. A regra continua conservadora: quando nao houver whitelist ou contrato mecanico validavel, a cascata e a matriz Fireworks escolhem Minimax/Kimi por regressao + Nash conforme custo e validade observada.

## Regra operacional

Se a regra precisa interpretar contexto amplo, ela nao e solver deterministico.

O caminho correto nesses casos e o decisor matricial escolher E2B ou Fireworks; o solver deve recusar.
