# Game Theory Model Selection

## Objetivo

Esta camada transforma a escolha de modelo em um jogo competitivo entre qualidade e custo.

O Track 1 pune dois erros simetricos:

- chamar modelo forte demais para uma tarefa simples;
- chamar modelo barato demais e perder accuracy.

O seletor agora trata esses erros como um dilema do prisioneiro: cada decisao pode cooperar com o objetivo global ou defectar para uma estrategia localmente sedutora.

## Jogadores

O jogo tem tres interesses:

- `accuracy_player`: maximizar aderencia da resposta ao dominio da tarefa.
- `token_budget_player`: minimizar custo de input/output Fireworks.
- `latency_tiebreaker`: desempatar em favor de menor latencia sem dominar custo/qualidade.

O equilibrio escolhido e a estrategia pura com maior produto de Nash dentro da fronteira elegivel.

## Matriz De Correlacao

Cada tarefa e mapeada para um dominio:

- `classification`
- `formatting`
- `summarization`
- `extraction`
- `logic`
- `math_reasoning`
- `code_debug`
- `code_generation`
- `current_factual`
- `general`

Cada modelo tem fortalezas:

- `general`
- `classification`
- `formatting`
- `summarization`
- `logic`
- `math_reasoning`
- `code_generation`
- `code_debug`
- `reasoning`
- `agentic`
- `embedding`
- `reranker`

A matriz `DOMAIN_CORRELATION_MATRIX` calcula o encaixe entre dominio da tarefa e fortalezas do modelo. Exemplos:

| Dominio da tarefa | Forca do modelo | Correlacao |
| --- | --- | --- |
| `code_generation` | `code_generation` | `1.00` |
| `code_generation` | `code_debug` | `0.85` |
| `code_generation` | `agentic` | `0.75` |
| `logic` | `math_reasoning` | `0.85` |
| `summarization` | `extraction` | `0.70` |
| `classification` | `general` | `0.55` |
| qualquer chat | `embedding`/`reranker` | `0.00` para resposta final |

Essa matriz impede um erro comum: comparar modelos apenas por preco quando eles nao sao igualmente correlacionados com a tarefa.

## Utilidades

Cada candidato recebe tres utilidades normalizadas:

```text
cost_utility = inverse_range(estimated_cost_usd)
latency_utility = inverse_range(latency_ms)
quality_utility =
  0.50 * capability_ratio
  + 0.30 * domain_correlation
  + 0.20 * reliability
```

`capability_ratio` e truncado em `1.0`. Depois que o modelo passa o piso minimo, o jogo nao recompensa infinitamente modelos maiores. Isso evita over-escalation.

## Pesos Por Tier

| Tier | Custo | Qualidade | Latencia |
| --- | ---: | ---: | ---: |
| `cheap` | `0.65` | `0.25` | `0.10` |
| `medium` | `0.50` | `0.35` | `0.15` |
| `strong` | `0.40` | `0.50` | `0.10` |

Interpretacao:

- em `cheap`, custo domina porque a tarefa deve ser quase mecanica;
- em `medium`, qualidade ganha peso, mas custo ainda lidera;
- em `strong`, qualidade lidera, mas custo ainda decide entre modelos suficientemente bons.

## Produto De Nash

O score principal e:

```text
nash_product =
  cost_utility ^ cost_weight
  * quality_utility ^ quality_weight
  * latency_utility ^ latency_weight
```

O modelo escolhido e:

```text
max(nash_product, prisoner_payoff, -estimated_cost_usd, -latency_ms)
```

Somente candidatos chat-capable e elegiveis competem na decisao final.

## Dilema Do Prisioneiro

Cada candidato recebe um rotulo estrategico:

| Label | Significado |
| --- | --- |
| `cooperate_token_efficient` | modelo passa o piso de qualidade e esta perto do menor custo elegivel |
| `cooperate_quality_safe` | modelo passa o piso de qualidade, mas nao e o menor custo |
| `defect_unsafe_underqualified` | modelo barato demais para o dominio |
| `defect_expensive_overescalation` | modelo forte, mas caro demais para ganho marginal de qualidade |
| `dominated_strategy` | existe outro modelo melhor ou igual em custo/latencia/capacidade/confiabilidade |
| `non_chat_auxiliary_strategy` | embedding/reranker; pode ajudar RAG, mas nao produz resposta final |

## Exemplo Pratico

Input:

```text
Write a function that parses nested JSON and handles edge cases.
```

Dominio:

```text
code_generation
```

No catalogo completo atual:

- `minimax-m3`: correlacao `1.0`, passa piso forte, custo baixo, vira `cooperate_token_efficient`.
- `kimi-k2p7-code`: correlacao `1.0`, qualidade alta, mas custo muito maior, vira `defect_expensive_overescalation`.
- `gpt-oss-20b`: custo muito baixo, mas capacidade insuficiente, vira `defect_unsafe_underqualified`.
- `qwen3-embedding-8b`: nao e chat, vira `non_chat_auxiliary_strategy`.

Equilibrio:

```text
accounts/fireworks/models/minimax-m3
```

Isso nao diz que M3 e "melhor" que Kimi em absoluto. Diz que, neste jogo especifico, ele e a melhor resposta estrategica dado o scoring token/accuracy.

## Onde Isso Mora No Codigo

Arquivo:

```text
router/orchestration/fireworks_model_router.py
```

Campos incluidos em cada candidato:

- `correlation`
- `quality_utility`
- `cost_utility`
- `latency_utility`
- `nash_product`
- `prisoner_payoff`
- `game_label`

Resumo da selecao:

- `game_theory.selection_rule`
- `game_theory.equilibrium_model`
- `game_theory.equilibrium_type`
- `game_theory.tier_weights`
- `game_theory.selected_nash_product`
- `game_theory.selected_prisoner_payoff`
- `game_theory.selected_correlation`

## Regra Competitiva

Se dois modelos sao suficientemente bons, ganha o que coopera melhor com o objetivo global: accuracy acima do piso com menor custo de tokens.

Se um modelo barato nao passa o piso, ele nao e economia; e risco.

Se um modelo caro nao melhora materialmente a qualidade, ele nao e seguranca; e over-escalation.
