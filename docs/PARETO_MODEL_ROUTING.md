# Pareto Model Routing

## Thesis

Track 1 is not a contest of the strongest model. It is a contest of efficient choice: for each input, select the model that delivers sufficient quality at the lowest possible token cost.

Capability research, training, and benchmarks by model family: [MODEL_CAPABILITY_RESEARCH.md](MODEL_CAPABILITY_RESEARCH.md).

Correlation matrix layer, Nash equilibrium, and prisoner's dilemma: [GAME_THEORY_MODEL_SELECTION.md](GAME_THEORY_MODEL_SELECTION.md).

Experimental matrix regression layer to calibrate weights with real microbenchmarks: [MATRIX_REGRESSION_SELECTION.md](MATRIX_REGRESSION_SELECTION.md).

This creates a Pareto frontier per task. A model is dominated when another model is simultaneously:

- cheaper or equal;
- faster or equal;
- as capable or more capable for that domain;
- as reliable or more reliable.

Dominated models should not receive traffic in that task profile.

## Input Signals

The router extracts lightweight signals from the prompt:

- `classification`: sentiment, positive/negative/neutral, simple label.
- `formatting`: JSON, uppercase, lowercase, return only, strict format.
- `summarization`: summarize, synthesize, reduce text.
- `extraction`: named entity, extract, entities.
- `logic`: puzzle, deductive, constraints, proof.
- `math_reasoning`: multi-step, percentage, rate, average, word problem.
- `code_debug`: debug, traceback, bug, fix code.
- `code_generation`: write a function, implement, code generation.
- `current_factual`: latest, today, current, price, CEO, version.
- `general`: fallback.

These signals become three tiers:

- `cheap`: short task, classification, or formatting.
- `medium`: general language, summarization, extraction, stable factual.
- `strong`: code, reasoning, multi-step math, temporal information.

## Model Metrics

Each candidate receives an estimated profile:

- input price per 1M tokens;
- output price per 1M tokens;
- observed or estimated latency;
- observed tokens in a simple task;
- strengths by domain;
- observed reliability.
- service path: `standard`, `priority`, or `fast`.
- model type: `chat`, `embedding`, or `reranker`.
- ability to respond via the chat/completions path.

The price comes from the Fireworks Serverless Pricing documentation. The latency and simple tokens come from the project's real microbenchmarks.

## Mapped Fireworks Catalog

Final response models, all via `accounts/fireworks/models/...`:

Note of 2026-07-08: Track 1 ACT II now has an official restricted Pareto. In the final path, consider only:

- `minimax-m3`;
- `kimi-k2p7-code`;
- `gemma-4-31b-it`;
- `gemma-4-26b-a4b-it`;
- `gemma-4-31b-it-nvfp4`.

The models below that do not belong to this list are for historical research/calibration, not as the final submission route.

| Model | Role in Pareto | Preferred Use |
| --- | --- | --- |
| `gpt-oss-20b` | lowest entry cost for chat | classification, simple formatting, short response |
| `deepseek-v4-flash` | cheap model and stronger than the basic one | summarization, general language, cheap fallback |
| `gpt-oss-120b` | cheap reasoning with `reasoning_effort` control | logic and strong tasks when specialized code is not needed |
| `minimax-m3` | best current cost/capability for code and agent | first candidate for `code_generation` and `code_debug` in the complete catalog |
| `minimax-m2p7` | cheap alternative for agent/productivity | fallback if M3 is not in `ALLOWED_MODELS` |
| `qwen3p7-plus` | multimodal middle ground with function calling | math, code, and multimodal tasks when allowed |
| `nemotron-3-ultra-nvfp4` | reasoning/code/math with average price | strong fallback before more expensive models |
| `kimi-k2p7-code` | specialized model for long-horizon code | complex code when confidence matters more than minimum cost |
| `kimi-k2p6` | previous agentic/coding model | Kimi fallback if K2.7 Code is not released |
| `glm-5p1` | broad model for language/structure | general, summarization, formatting, logic |
| `glm-5p2` | newer GLM with long context | general, summarization, formatting, logic, long prompts |
| `deepseek-v4-pro` | strong model for reasoning/code | high reliability fallback, expensive and slow |

Auxiliary models, not used for final response:

| Model | Type | Rule |
| --- | --- | --- |
| `qwen3-embedding-8b` | `embedding` | can support future RAG/eval, but never wins the chat route |
| `qwen3-reranker-8b` | `reranker` | can support future ranking, but never wins the chat route |

Critical rule: if `ALLOWED_MODELS` comes with only embedding/reranker, the router fails early with a clear error. This is better than wasting a Fireworks call on an endpoint that does not produce the response required by Track 1.

## Service Paths

Fireworks Serverless has three paths:

- `standard`: default, no extra parameter. It is the happy path for Track 1.
- `priority`: activated by `service_tier=priority`, more reliable under peak load and more expensive. Should be a manual fallback, not the default.
- `fast`: selected by another model ID, for example `accounts/fireworks/routers/glm-5p2-fast`. Enters the Pareto only if the ID appears in `ALLOWED_MODELS`.

Fast may be on the frontier for latency, but it should not win when Standard already has sufficient capability and lower cost.

## Prompt Cache

Prompt caching is default in Fireworks and works by exact prefix. To increase cache hit:

- keep system prompt static;
- place variable input at the end;
- do not insert timestamp in the system prompt;
- send `user=track1-token-router-v1` as a session affinity hint.

## Decision Rule

1. Read `ALLOWED_MODELS`.
2. Classify input into domain and tier.
3. Assemble candidates with estimated cost.
4. Separate chat models from auxiliary models.
5. Remove dominated models.
6. Filter models with minimum capability for the tier.
7. Choose the lowest cost within the eligible frontier.
8. Apply economical `reasoning_effort` when supported.
9. If the model rejects the extra parameter, retry once without it.

## Field Findings

In real microbenchmarks, `reasoning_effort=none` reduced trivial tasks to 13-18 total tokens in GLM, DeepSeek, and Kimi. Without reasoning control, some models spent 68-95 tokens, and GLM even returned reasoning within the `content`.

`gpt-oss-120b` rejected `reasoning_effort=none`, but accepted `low`.

In the real Pareto microbenchmark from 2026-07-07, with 36 calls and total estimated cost of `0.00275120` USD:

- `deepseek-v4-flash`, `minimax-m3`, and `kimi-k2p7-code` completed 6/6 valid mechanical tasks;
- `deepseek-v4-flash` was the best cost/validity on the small dataset;
- `gpt-oss-120b` went from 4/6 in `auto` to 6/6 when forced to `reasoning_effort=low`;
- `gpt-oss-20b` went up to 5/6 with `low`, but still failed in logic due to empty content;
- `qwen3p7-plus` failed in strict tasks by returning reasoning along with the response.

In a new round on 2026-07-08, with `select_reasoning_effort()` using `low` for `gpt-oss`, the same microbenchmark produced:

- 36 calls, 33 valid, estimated cost of `0.00281451` USD;
- `deepseek-v4-flash`, `gpt-oss-20b`, `gpt-oss-120b`, `minimax-m3`, and `kimi-k2p7-code` completed 6/6;
- `qwen3p7-plus` repeated 3/6 and remains out of the strict path until we control thinking/output;
- by cost, `deepseek-v4-flash` won in `formatting`, `classification`, and `logic`;
- by cost, `gpt-oss-20b` won in `math_reasoning` and `code_generation`;
- by latency, `gpt-oss-120b` was surprisingly strong in short tasks, despite the higher cost than `gpt-oss-20b` and `deepseek-v4-flash`.

Round restricted to official models accessible on the local key on 2026-07-08:

- dataset: `evals/fireworks-pareto/track1-category-microbench.jsonl`;
- categories: factual Q&A, math reasoning, sentiment, summarization, NER, code debugging, logic puzzles, and code generation;
- tested models: `minimax-m3`, `kimi-k2p7-code`;
- calls: `32`;
- valid: `29/32`;
- estimated cost: `0.00517850` USD;
- `minimax-m3`: `15/16`, cost `0.00141390`, average latency `1330ms`;
- `kimi-k2p7-code`: `14/16`, cost `0.00376460`, average latency `2008ms`;
- operational conclusion: `minimax-m3` is the strongest accessible default; `kimi-k2p7-code` should be a fallback/candidate, not the default.

Gemma in the current state:

- the three official Gemmas return `HTTP 404` with the current local key;
- the router is prepared to choose Gemma in cheap/medium tasks if the harness permits;
- if Gemma fails, the runner tries the next allowed model before returning an error.

## Competitive Implication

The router should not:

- always use the smallest model;
- always use the largest model;
- always use Gemma;
- always use the first from `ALLOWED_MODELS`.

The router should be:

- Gemma-first only in cheap/medium language, if Gemma is accessible;
- Minimax-first for strong math, logic, code debugging, and code generation;
- cost-first when the task is simple;
- capability-first when the task is strong;
- always `ALLOWED_MODELS`-first in the official path.
