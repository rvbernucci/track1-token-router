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
hybrid_score =
  0.50 * regression_utility
  + 0.30 * nash_product
  + 0.20 * cost_utility
```

## Artefatos

- Codigo: `router/orchestration/matrix_regression_selector.py`
- Fit offline: `scripts/fit_fireworks_matrix_regression.py`
- Pesos gerados: `reports/generated/fireworks-matrix-regression-weights.json`
- Relatorio: `reports/generated/fireworks-matrix-regression-report.md`

## Resultado Atual

Treino com 48 linhas:

- `reports/generated/fireworks-microbench-results.jsonl`
- `reports/generated/fireworks-microbench-gpt-low-results.jsonl`

Top coeficientes aprendidos no fit atual:

| Feature | Sinal |
| --- | ---: |
| `family_qwen` | negativo |
| `reasoning_medium` | negativo |
| `reasoning_low` | positivo |
| `family_deepseek` | positivo |
| `family_minimax` | positivo |
| `domain_math_reasoning` | positivo |

Replay atual:

| Task | Modelo escolhido |
| --- | --- |
| `cheap_exact_ack` | `gpt-oss-20b` |
| `cheap_sentiment` | `gpt-oss-20b` |
| `format_json` | `gpt-oss-20b` |
| `code_static` | `minimax-m3` |
| `logic_exact` | `deepseek-v4-flash` |
| `math_exact` | `deepseek-v4-flash` |

## Leitura Competitiva

A regressao confirmou alguns sinais fortes:

- `reasoning_effort=medium` prejudicou `gpt-oss` com budget curto;
- `reasoning_effort=low` e melhor default para `gpt-oss`;
- `qwen3p7-plus` precisa de controle de overthinking antes de entrar em resposta estrita;
- `deepseek-v4-flash` parece subestimado pelo Pareto manual em tarefas curtas e raciocinio simples;
- `minimax-m3` continua bom candidato para codigo.

## Limite Atual

O dataset ainda e pequeno. A regressao ja e util para calibrar, mas ainda nao deve substituir o seletor principal.

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
