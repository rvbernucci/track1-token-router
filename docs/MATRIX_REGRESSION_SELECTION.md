# Matrix Regression Model Selection

## Objetivo

Criar uma camada experimental para aprender pesos a partir dos microbenchs reais Fireworks.

A ideia nao e substituir o Pareto/Nash imediatamente. A ideia e usar regressao matricial para calibrar a relacao entre:

- dominio da tarefa;
- familia do modelo;
- capacidade estimada;
- correlacao de dominio;
- custo estimado;
- latencia estimada;
- modo de reasoning;
- validade observada;
- custo/latencia reais.

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
  + 0.15 * observed_cost_utility
  + 0.05 * observed_latency_utility
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

| Tier | Regressao | Nash | Custo |
| --- | ---: | ---: | ---: |
| `cheap` | 0.55 | 0.25 | 0.20 |
| `medium` | 0.70 | 0.20 | 0.10 |
| `strong` | 0.85 | 0.10 | 0.05 |

A ideia competitiva e simples: em tarefa forte, primeiro passar pelo accuracy gate; em tarefa barata, reduzir tokens agressivamente.

## Artefatos

- Codigo: `router/orchestration/matrix_regression_selector.py`
- Fit offline: `scripts/fit_fireworks_matrix_regression.py`
- Pesos Track 1 usados no Docker: `router/data/fireworks_track1_allowed_weights.json`
- Relatorio Track 1: `reports/generated/fireworks-track1-allowed-20260709-regression.md`
- Resultado Fireworks real: `reports/generated/fireworks-track1-category-20260709-results.jsonl`

## Resultado Atual

Treino Track 1 permitido com 80 linhas:

- `minimax-m3`
- `kimi-k2p7-code`
- `gemma-4-31b-it`
- `gemma-4-26b-a4b-it`
- `gemma-4-31b-it-nvfp4`

Top coeficientes aprendidos no fit atual:

| Feature | Sinal |
| --- | ---: |
| `family_minimax` | positivo |
| `family_kimi` | positivo |
| `interaction_minimax_code_debug` | negativo |
| `interaction_kimi_code_debug` | positivo |
| `interaction_minimax_math` | positivo |
| `interaction_minimax_code_generation` | positivo |

Replay atual:

| Task | Modelo escolhido |
| --- | --- |
| `debug_first_even` | `kimi-k2p7-code` |
| `debug_is_adult` | `kimi-k2p7-code` |
| `code_gen_clamp` | `minimax-m3` |
| `math_discount_fee` | `minimax-m3` |
| `ner_money_date` | `minimax-m3` |
| `sentiment_positive` | `minimax-m3` |

## Leitura Competitiva

A regressao confirmou alguns sinais fortes:

- `minimax-m3` e o melhor default empirico para a maioria dos dominios Track 1 observados;
- `kimi-k2p7-code` deve ser escalado para code debugging quando a tarefa pede correcao de codigo existente;
- Gemma serverless segue indisponivel na chave local, entao o runner precisa tentar, cachear 404 e seguir sem travar;
- interacoes familia x dominio sao necessarias, porque uma media global por modelo esconde especializacoes.

## Limite Atual

O dataset ainda e pequeno, mas a regressao agora esta ativa como camada de calibracao do seletor principal no Docker. Ela nao substitui Nash: ela o combina com o score aprendido.

Principal lacuna:

- o roteador ainda usa custo estimado por perfil;
- o microbench mostrou que custo real pode divergir por tokens gerados;
- proximo passo e regressao de `observed_tokens` por modelo/dominio/modo de reasoning.

## Proximo Passo

Implementar uma segunda regressao:

```text
predicted_completion_tokens = f(model_family, domain, tier, reasoning_mode)
```

Com isso, o Pareto deixa de usar apenas preco oficial e passa a estimar custo real esperado:

```text
expected_cost =
  prompt_tokens * input_price
  + predicted_completion_tokens * output_price
```

Essa provavelmente e a maior melhoria para escolher entre `gpt-oss-20b` e `deepseek-v4-flash` em tarefas cheap.
