# Pareto Model Routing

## Tese

Track 1 nao e uma disputa de modelo mais forte. E uma disputa de escolha eficiente: para cada input, selecionar o modelo que entrega qualidade suficiente com o menor custo de tokens possivel.

Pesquisa de capacidades, treinamento e benchmarks por familia de modelo: [MODEL_CAPABILITY_RESEARCH.md](MODEL_CAPABILITY_RESEARCH.md).

Camada de matriz de correlacao, equilibrio de Nash e dilema do prisioneiro: [GAME_THEORY_MODEL_SELECTION.md](GAME_THEORY_MODEL_SELECTION.md).

Camada experimental de regressao matricial para calibrar pesos com microbench real: [MATRIX_REGRESSION_SELECTION.md](MATRIX_REGRESSION_SELECTION.md).

Isso cria uma fronteira de Pareto por tarefa. Um modelo e dominado quando outro modelo e ao mesmo tempo:

- mais barato ou igual;
- mais rapido ou igual;
- tao capaz ou mais capaz para aquele dominio;
- tao confiavel ou mais confiavel.

Modelos dominados nao deveriam receber trafego naquele perfil de tarefa.

## Sinais Do Input

O router extrai sinais leves do prompt:

- `classification`: sentimento, positivo/negativo/neutro, label simples.
- `formatting`: JSON, uppercase, lowercase, return only, formato estrito.
- `summarization`: resumir, sintetizar, reduzir texto.
- `extraction`: named entity, extract, entities.
- `logic`: puzzle, deductive, constraints, proof.
- `math_reasoning`: multi-step, percentage, rate, average, word problem.
- `code_debug`: debug, traceback, bug, fix code.
- `code_generation`: write a function, implement, code generation.
- `current_factual`: latest, today, current, price, CEO, version.
- `general`: fallback.

Esses sinais viram tres tiers:

- `cheap`: tarefa curta, classificacao ou formato.
- `medium`: linguagem geral, resumo, extracao, factual estavel.
- `strong`: codigo, raciocinio, matematica multi-step, informacao temporal.

## Metricas Do Modelo

Cada candidato recebe um perfil estimado:

- preco de input por 1M tokens;
- preco de output por 1M tokens;
- latencia observada ou estimada;
- tokens observados em tarefa simples;
- fortalezas por dominio;
- confiabilidade observada.
- caminho de servico: `standard`, `priority` ou `fast`.
- tipo do modelo: `chat`, `embedding` ou `reranker`.
- capacidade de responder pelo caminho de chat/completions.

O preco veio da documentacao de Serverless Pricing da Fireworks. A latencia e tokens simples vieram do microbench real do projeto.

## Catalogo Fireworks Mapeado

Modelos de resposta final, todos via `accounts/fireworks/models/...`:

Nota de 2026-07-08: o Track 1 ACT II passou a ter Pareto restrito oficial. No caminho final, considerar apenas:

- `minimax-m3`;
- `kimi-k2p7-code`;
- `gemma-4-31b-it`;
- `gemma-4-26b-a4b-it`;
- `gemma-4-31b-it-nvfp4`.

Os modelos abaixo que nao pertencem a essa lista ficam como pesquisa/calibracao historica, nao como rota final de submissao.

| Modelo | Papel no Pareto | Uso preferencial |
| --- | --- | --- |
| `gpt-oss-20b` | menor custo de entrada para chat | classificacao, formato simples, resposta curta |
| `deepseek-v4-flash` | modelo barato e mais forte que o basico | resumo, linguagem geral, fallback barato |
| `gpt-oss-120b` | raciocinio barato com controle de `reasoning_effort` | logica e tarefas fortes quando codigo especializado nao e necessario |
| `minimax-m3` | melhor custo/capacidade atual para codigo e agente | primeiro candidato para `code_generation` e `code_debug` no catalogo completo |
| `minimax-m2p7` | alternativa barata para agente/produtividade | fallback se M3 nao estiver em `ALLOWED_MODELS` |
| `qwen3p7-plus` | meio termo multimodal com function calling | matematica, codigo e tarefas multimodais quando permitido |
| `nemotron-3-ultra-nvfp4` | raciocinio/codigo/matematica com preco medio | fallback forte antes de modelos mais caros |
| `kimi-k2p7-code` | modelo especializado em codigo long-horizon | codigo complexo quando a confianca importa mais que custo minimo |
| `kimi-k2p6` | modelo agentico/coding anterior | fallback de Kimi se K2.7 Code nao estiver liberado |
| `glm-5p1` | modelo amplo para linguagem/estrutura | general, resumo, formato, logica |
| `glm-5p2` | GLM mais novo com contexto longo | general, resumo, formato, logica, prompts longos |
| `deepseek-v4-pro` | modelo forte para raciocinio/codigo | fallback de alta confiabilidade, caro e lento |

Modelos auxiliares, nao usados para resposta final:

| Modelo | Tipo | Regra |
| --- | --- | --- |
| `qwen3-embedding-8b` | `embedding` | pode apoiar RAG/eval futura, mas nunca vence a rota de chat |
| `qwen3-reranker-8b` | `reranker` | pode apoiar ranking futuro, mas nunca vence a rota de chat |

Regra critica: se `ALLOWED_MODELS` vier apenas com embedding/reranker, o router falha cedo com erro claro. Isso e melhor do que gastar chamada Fireworks em endpoint que nao produz a resposta exigida pelo Track 1.

## Caminhos De Servico

Fireworks Serverless tem tres caminhos:

- `standard`: default, sem parametro extra. E o caminho feliz do Track 1.
- `priority`: ativado por `service_tier=priority`, mais confiavel em pico e mais caro. Deve ser fallback manual, nao padrao.
- `fast`: selecionado por outro model ID, por exemplo `accounts/fireworks/routers/glm-5p2-fast`. Entra no Pareto somente se o ID aparecer em `ALLOWED_MODELS`.

Fast pode estar na fronteira por latencia, mas nao deve vencer quando Standard ja tem capacidade suficiente e menor custo.

## Prompt Cache

Prompt caching e default na Fireworks e funciona por prefixo exato. Para aumentar cache hit:

- manter system prompt estatico;
- colocar input variavel no final;
- nao inserir timestamp no system prompt;
- enviar `user=track1-token-router-v1` como pista de afinidade de sessao.

## Regra De Decisao

1. Ler `ALLOWED_MODELS`.
2. Classificar o input em dominio e tier.
3. Montar candidatos com custo estimado.
4. Separar modelos de chat de modelos auxiliares.
5. Remover modelos dominados.
6. Filtrar modelos com capacidade minima para o tier.
7. Escolher o menor custo dentro da fronteira elegivel.
8. Aplicar `reasoning_effort` economico quando suportado.
9. Se o modelo rejeitar o parametro extra, refazer uma vez sem ele.

## Descoberta De Campo

Em microbench real, `reasoning_effort=none` reduziu tarefas triviais para 13-18 tokens totais em GLM, DeepSeek e Kimi. Sem controle de reasoning, alguns modelos gastaram 68-95 tokens e, em GLM, chegaram a retornar raciocinio no `content`.

`gpt-oss-120b` rejeitou `reasoning_effort=none`, mas aceitou `low`.

Em microbench Pareto real de 2026-07-07, com 36 chamadas e custo estimado total de `0.00275120` USD:

- `deepseek-v4-flash`, `minimax-m3` e `kimi-k2p7-code` fizeram 6/6 tarefas mecanicas validas;
- `deepseek-v4-flash` foi o melhor custo/validade no dataset pequeno;
- `gpt-oss-120b` caiu de 4/6 em `auto` para 6/6 quando forcado para `reasoning_effort=low`;
- `gpt-oss-20b` subiu para 5/6 com `low`, mas ainda falhou em logica por content vazio;
- `qwen3p7-plus` falhou em tarefas estritas por devolver raciocinio junto com a resposta.

Em nova rodada de 2026-07-08, com `select_reasoning_effort()` usando `low` para `gpt-oss`, o mesmo microbench produziu:

- 36 chamadas, 33 validas, custo estimado `0.00281451` USD;
- `deepseek-v4-flash`, `gpt-oss-20b`, `gpt-oss-120b`, `minimax-m3` e `kimi-k2p7-code` fizeram 6/6;
- `qwen3p7-plus` repetiu 3/6 e segue fora do caminho estrito ate controlarmos thinking/output;
- por custo, `deepseek-v4-flash` venceu `formatting`, `classification` e `logic`;
- por custo, `gpt-oss-20b` venceu `math_reasoning` e `code_generation`;
- por latencia, `gpt-oss-120b` ficou surpreendentemente forte em tarefas curtas, apesar do custo maior que `gpt-oss-20b` e `deepseek-v4-flash`.

Rodada restrita aos modelos oficiais acessiveis na chave local em 2026-07-08:

- dataset: `evals/fireworks-pareto/track1-category-microbench.jsonl`;
- categorias: factual Q&A, math reasoning, sentiment, summarization, NER, code debugging, logic puzzles e code generation;
- modelos testados: `minimax-m3`, `kimi-k2p7-code`;
- chamadas: `32`;
- validas: `29/32`;
- custo estimado: `0.00517850` USD;
- `minimax-m3`: `15/16`, custo `0.00141390`, latencia media `1330ms`;
- `kimi-k2p7-code`: `14/16`, custo `0.00376460`, latencia media `2008ms`;
- conclusao operacional: `minimax-m3` e o default acessivel mais forte; `kimi-k2p7-code` deve ser fallback/candidato, nao default.

Gemma no estado atual:

- os tres Gemma oficiais retornam `HTTP 404` com a chave local atual;
- o router esta preparado para escolher Gemma em tarefas cheap/medium se o harness liberar;
- se Gemma falhar, o runner tenta o proximo modelo permitido antes de devolver erro.

## Implicacao Competitiva

O router nao deve ser:

- sempre usar o menor modelo;
- sempre usar o maior modelo;
- sempre usar Gemma;
- sempre usar o primeiro de `ALLOWED_MODELS`.

O router deve ser:

- Gemma-first apenas em cheap/medium linguagem, se Gemma estiver acessivel;
- Minimax-first para strong math, logic, code debugging e code generation;
- custo-first quando a tarefa for simples;
- capacidade-first quando a tarefa for forte;
- sempre `ALLOWED_MODELS`-first no caminho oficial.
