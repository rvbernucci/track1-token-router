# Matrix Regression Model Selection

## Objetivo

Criar uma camada experimental para aprender pesos a partir dos microbenchs reais Fireworks.

A ideia nao e substituir o Pareto/Nash imediatamente. A ideia e usar regressao matricial para calibrar a relacao entre:

- dominio da tarefa;
- familia do modelo;
- capacidade estimada;
- correlacao de dominio;
- tokens estimados;
- custo estimado;
- latencia estimada;
- modo de reasoning;
- validade observada;
- tokens/custo/latencia reais.

## Formula

Cada candidato vira um vetor:

```text
x = [
  bias,
  tier flags,
  domain flags,
  capability,
  correlation,
  reliability,
  cost_utility,
  token_utility,
  latency_utility,
  nash_product,
  prisoner_payoff,
  family flags,
  family x domain interaction flags,
  reasoning flags
]
```

O alvo de treino combina validade e eficiencia observada:

```text
target =
  0.80 * valid
  + 0.14 * observed_token_utility
  + 0.04 * observed_cost_utility
  + 0.02 * observed_latency_utility
```

Os coeficientes sao aprendidos por ridge regression:

```text
beta = inv(XT X + lambda I) XT y
```

No runtime experimental:

```text
regression_utility = clamp(beta dot x, 0, 1)
```

O `hybrid_score` muda por tier:

| Tier | Regressao | Nash | Tokens | Custo |
| --- | ---: | ---: | ---: | ---: |
| `cheap` | 0.50 | 0.20 | 0.20 | 0.10 |
| `medium` | 0.65 | 0.15 | 0.15 | 0.05 |
| `strong` | 0.80 | 0.10 | 0.08 | 0.02 |

A ideia competitiva e simples: em tarefa forte, primeiro passar pelo accuracy gate; em tarefa barata, reduzir tokens agressivamente.

## Artefatos

- Codigo: `router/orchestration/matrix_regression_selector.py`
- Fit offline: `scripts/fit_fireworks_matrix_regression.py`
- Pesos Track 1 usados no Docker: `router/data/fireworks_track1_allowed_weights.json`
- Relatorio Track 1: `reports/generated/fireworks-track1-allowed-20260709-regression.md`
- Resultados Fireworks reais: `reports/generated/fireworks-track1-category-20260709-results.jsonl`, `reports/generated/fireworks-hidden-variant-results.jsonl`, `reports/generated/fireworks-championship-results.jsonl`, `reports/generated/fireworks-frontier-20260709-results.jsonl`, `reports/generated/fireworks-structure-heldout-20260709-results.jsonl`

## Resultado Atual

Treino Track 1 permitido com `151` linhas uteis, filtradas de `487` linhas brutas:

- `minimax-m3`
- `kimi-k2p7-code`

As linhas `ok=false` sao excluidas por padrao para nao confundir erro de acesso/transporte com qualidade do modelo. Os pesos tambem registram `observed_models`; no runtime matricial, modelos permitidos mas sem nenhuma chamada concluida no treino sao filtrados quando ha alternativa observada. Isso evita escolher Gemma cegamente enquanto os IDs serverless seguem retornando `404` na chave local.

Os pesos agora tambem registram uma matriz empirica `domain_model_stats` em dois niveis: `dominio::estrutura` e `dominio`. No runtime, cada candidato recebe ajuste por taxa de validade suavizada e confianca primeiro por estrutura especifica, depois por dominio, depois por media geral. Isso evita que uma opcao barata com historico ruim naquele formato vire estrategia dominante so por custo/tokens.

Top coeficientes aprendidos no fit atual:

| Feature | Sinal |
| --- | ---: |
| `bias` | positivo |
| `shape_json_numeric` | negativo |
| `shape_constrained_summary` | negativo |
| `shape_json_output` | positivo |
| `shape_direct_numeric` | negativo |
| `shape_json_extraction` | negativo |
| `shape_word_problem` | negativo |
| `correlation` | positivo |
| `interaction_kimi_math` | positivo |
| `interaction_kimi_code_debug` | negativo |

Replay atual:

| Task | Modelo escolhido |
| --- | --- |
| `factual_author` | `kimi-k2p7-code` |
| `summarization_tokens` | `kimi-k2p7-code` |
| `debug_first_even` | `kimi-k2p7-code` |
| `debug_is_adult` | `kimi-k2p7-code` |
| `code_gen_clamp` | `minimax-m3` |
| `math_discount_fee` | `minimax-m3` |
| `ner_money_date` | `minimax-m3` |
| `sentiment_positive` | `kimi-k2p7-code` |

## Leitura Competitiva

A regressao confirmou alguns sinais fortes:

- `kimi-k2p7-code` deve vencer quando a validade observada e comparavel e o `usage.total` observado por dominio/estrutura/modelo e menor, especialmente em factual QA, formatting, logic, math direto e code debugging;
- `minimax-m3` continua forte como fallback de robustez, especialmente em code generation, extraction estruturada e math composto quando o score calibrado supera a economia de tokens;
- Gemma serverless segue indisponivel na chave local, entao o runner precisa tentar, cachear 404 e seguir sem travar;
- interacoes familia x dominio sao necessarias, porque uma media global por modelo esconde especializacoes.

## Limite Atual

O dataset ainda e pequeno, mas a regressao agora esta ativa como camada de calibracao do seletor principal no Docker. Ela nao substitui Nash: ela o combina com o score aprendido.

Principal lacuna:

- a estimativa runtime de tokens ja mistura perfil teorico com `avg_total_tokens` observado por dominio/estrutura/modelo, ponderado pela confianca da amostra;
- os microbenches frontier e structure-heldout mostraram que verbosidade e validade variam por familia e formato de pergunta;
- proximo passo e separar `prompt_tokens` e `completion_tokens` quando o provedor retornar esses campos de forma estavel, para calibrar melhor respostas longas.

## Proximo Passo

Implementar uma segunda regressao quando houver amostra suficiente:

```text
predicted_completion_tokens = f(model_family, domain, tier, reasoning_mode)
```

Com isso, o Pareto deixa de usar apenas `avg_total_tokens` observado e passa a estimar custo real esperado por componente:

```text
expected_cost =
  prompt_tokens * input_price
  + predicted_completion_tokens * output_price
```

Essa provavelmente e a maior melhoria para escolher entre `gpt-oss-20b` e `deepseek-v4-flash` em tarefas cheap.
