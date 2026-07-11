# Mechanical Validator And Solver Pack

## Championship False-Positive Audit

On the frozen 571-task validation/test corpus, the pre-hardening registry accepted 14 tasks. Independent Claude Sonnet 5 and Gemini judges agreed that 13 were incorrect and one was correct. Incidental `max`, `lowercase`, character-count and JSON-schema language had triggered solvers outside their complete contracts.

The championship revision replaced those keyword checks with full task-contract matches and explicit code/JSON guards. Replaying the same 571 tasks produced zero acceptances and 571 safe refusals. Deterministic execution remains available only for the separately tested exact-template pack; broad corpus prompts fall through to E2B or Fireworks.

## Role

The solver pack resolves mechanical tasks before the model path in `ROUTER_MODE=competition`.

It exists to save latency and reduce risk when the response can be calculated or transformed with high confidence by code.

It is not the core intelligence of Track 1. The core is the general-purpose agent that interprets the task, chooses the smallest sufficient model in `ALLOWED_MODELS`, and preserves accuracy. This pack is the security layer: schema, format, narrow calculations, and mechanical verifications.

## Active Solvers

| solver | covers | safety limit |
|---|---|---|
| `arithmetic` | addition, subtraction, multiplication, exact integer division, and explicit arithmetic mean | only short integer expressions or the phrase `scores -> arithmetic mean` |
| `percent_fee_math` | single percentage discount followed by a fixed fee; explicit repeated percentage increase | requires a verifiable textual formula and limited percentages |
| `proportional_rate` | linear rate of identical units | requires a phrase with identical units, total production, and a new number of units |
| `numeric_compare` | greater/lesser between two numbers; JSON min/max; JSON sum/product | requires a short numeric list or exactly two numbers and a comparison keyword |
| `stable_factual_qa` | stable facts of extremely high confidence | only whitelist exact-prompt with `return only`; blocks `today/latest/current/now/as of` |
| `sentiment_lexicon` | explicit sentiment `positive/neutral/negative` | requires a sentiment prompt, `Text:` marker, and clear lexical margin or factual neutral phrase |
| `constrained_summary` | short summaries with word limits and mandatory/inferable terms | only templates that mechanically obey `at most N words` |
| `entity_extract` | minified JSON and simple fields for mechanical NER patterns | only dated payment, invoice/date/amount, person/org/city foundation, customer/item/city purchase/order, key/value pairs, simple names, title, and invoice code |
| `logic_ordering` | simple transitive ordering endpoint and narrow quantified syllogisms | requires nominal comparative relations, single endpoint, or verifiable `all/no` / `all/some` pattern |
| `modus_ponens` | inference `if A then B; A; is B?` | responds only `yes` when normalized antecedent and consequent match exactly |
| `python_code_debug` | Python fixes for known trivial bugs | only signatures and exact symptoms tested by `python_function_cases` |
| `python_code_generation` | small Python utility functions of common use | only templates without `import`, executable by the secure validator |
| `char_count` | character count | requires string in quotes |
| `word_count` | word count | requires string in quotes |
| `case_transform` | uppercase, lowercase, titlecase | requires string in quotes or mechanical marker `version of this text:` |
| `whitespace` | trim and normalization of whitespace | requires string in quotes |
| `json_transform` | JSON compact and pretty | requires valid JSON payload |
| `list_item` | first/last item and small ordinals | only simple JSON list or comma-separated list |

## Deliberate Blocks

- Algebra, equations, derivatives, and integrals are out.
- Relative or ambiguous dates are out.
- Broad word problems are out, even when they seem calculable.
- Non-integer division and division by zero are out.
- Tasks that request sorting are out, even if they also request the first/last item.
- Unquoted strings are out in count solvers; unquoted transformation only enters with the `this text:` marker.
- Mixed sentiment or sentiment without lexical margin is out.
- Generic NER is out; the solver only enters in verifiable structural patterns.
- Generic Factual QA is out; only stable facts explicitly whitelisted enter.
- Open summarization is out; only short summaries with mechanically verifiable constraints enter.
- Logic with contrapositive, affirming the consequent, or disconnected graphs is out.
- Generic programming is out; Python templates only enter when the signature, verb, and criteria match exactly.
- Python templates do not use `import`, `open`, `eval`, classes, or global state, to remain compatible with the secure validator of the microbench.

## Track 1 Payoff

Track 1 includes factual Q&A, math reasoning, sentiment, summarization, NER, code debugging, logic puzzles, and code generation.

This pack does not attempt to replace models in these eight categories. It removes from the remote path only the subcases where code is more reliable than LLMs:

- mechanical math reasoning with a single formula;
- stable factual QA in a narrow whitelist;
- obvious sentiment with explicitly polarized vocabulary;
- short summarization with a word limit and mandatory terms;
- structural NER in regular sentences;
- logic puzzles of a single inference or a short transitive chain;
- code debugging/code generation in small, executable Python templates;
- format transformations and counting.

The expected gain is to reduce Fireworks calls without dropping the accuracy gate. When the pattern is not clear, `solve_deterministic` returns `None` and the model router continues normally.

## Regression Gate

Before touching any solver, run:

```bash
python3 scripts/track1_deterministic_coverage.py --check
```

This gate runs the local Track 1 microbenches with `CompetitionRunner` in dry-run, validates only `solver_*` and `guardrail_*` routes against the dataset validators, and fails if:

- any verifiable deterministic output is incorrect;
- the deterministic coverage falls below the configured floor.

The same gate also runs inside `scripts/offline_release_check.sh`.

Current result on the local championship, hidden-variant, adversarial-hidden, frontier, and structure-heldout datasets: `111/111` tasks resolved by deterministic route or guardrail, with `100%` validity on deterministic outputs.

The dataset `evals/fireworks-pareto/adversarial-hidden-microbench.jsonl` was added as an anti-overfitting gate. It covers mechanical variants of factual QA, math, sentiment, summarization, NER, logic puzzles, code debugging, code generation, and formatting. The goal is not to simulate open knowledge; it is to prove that strictly verifiable subcases continue to output with zero remote tokens even when the phrasing changes.

A complementary runtime eval with a purposefully unreachable Fireworks endpoint validated `108/108` unique deduplicated tasks, `fireworks_tasks=0`, `remote_tokens.total=0`, and a cost of `$0.00` in `reports/generated/fireworks-runtime-zero-token-111-report.md`.

The generated report also lists remaining non-deterministic routes. As of 2026-07-09, the extended gate has no non-deterministic routes in the six local microbenches, but this does not mean that every factual QA or summarization should become code. The rule remains conservative: when there is no whitelist or verifiable mechanical contract, the cascade and the Fireworks matrix select Minimax/Kimi via regression + Nash according to cost and observed validity.

## Operational Rule

If the rule needs to interpret broad context, it is not a deterministic solver.

The correct path in these cases is for the matrix decision-maker to choose E2B or Fireworks; the solver must refuse.
