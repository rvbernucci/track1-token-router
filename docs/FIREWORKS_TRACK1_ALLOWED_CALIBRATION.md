# Fireworks Track 1 Allowed Models Calibration

Last run: 2026-07-09

Primary dataset: `evals/fireworks-pareto/track1-category-microbench.jsonl`

Hidden-variant dataset: `evals/fireworks-pareto/hidden-variant-microbench.jsonl`

Command shape:

```bash
python3 scripts/fireworks_microbench.py \
  --dataset evals/fireworks-pareto/track1-category-microbench.jsonl \
  --models "minimax-m3,kimi-k2p7-code,gemma-4-31b-it,gemma-4-26b-a4b-it,gemma-4-31b-it-nvfp4" \
  --max-calls 80 \
  --budget-usd 2.00 \
  --max-tokens 128
```

Latest primary result file: `reports/generated/fireworks-track1-category-20260709-results.jsonl`

Latest hidden-variant result file: `reports/generated/fireworks-hidden-variant-results.jsonl`

Latest championship result file: `reports/generated/fireworks-championship-results.jsonl`

Latest primary report: `reports/generated/fireworks-track1-category-20260709-report.md`

Latest hidden-variant report: `reports/generated/fireworks-hidden-variant-report.md`

Actual estimated spend: `$0.00448690` primary + `$0.00213260` hidden variants = `$0.00661950`.

## Aggregate Results

| Model | Valid | Calls | Error Calls | Tokens | Estimated Cost USD | Avg Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `accounts/fireworks/models/minimax-m3` | 15 | 16 | 1 | 2876 | 0.00123090 | 1814 |
| `accounts/fireworks/models/kimi-k2p7-code` | 16 | 16 | 0 | 1607 | 0.00325600 | 3226 |
| `accounts/fireworks/models/gemma-4-31b-it` | 0 | 16 | 16 | 0 | 0.00000000 | 410 |
| `accounts/fireworks/models/gemma-4-26b-a4b-it` | 0 | 16 | 16 | 0 | 0.00000000 | 353 |
| `accounts/fireworks/models/gemma-4-31b-it-nvfp4` | 0 | 16 | 16 | 0 | 0.00000000 | 361 |

## Observations

- `minimax-m3` is the current cheapest high-accuracy Fireworks fallback among accessible Track 1 allowed models.
- `kimi-k2p7-code` is more expensive and slower, but it was the only accessible model with `16/16` valid answers in this run.
- Domain winner policy changed: `kimi-k2p7-code` is preferred for `code_debug`; `minimax-m3` is preferred for code generation, math, logic, factual, sentiment, summarization and NER unless future calibration says otherwise.
- Hidden-variant rerun: both accessible models passed `8/8`; `minimax-m3` cost `$0.00070650`, while `kimi-k2p7-code` cost `$0.00142610`.
- The three Gemma serverless IDs returned `HTTP 404 Not Found` with the current local Fireworks key.
- Gemma should remain in the architecture through AMD local inference and should still be attempted when the official harness exposes it, but repeated 404s should be cached and skipped within a batch.
- NER data/date/currency tasks need explicit formatting instructions in our evals; otherwise semantic normalization can look like a mechanical failure.

After tightening the `ner_money_date` prompt to require date and amount exactly as shown in the source text, a two-call retest with `minimax-m3` and `kimi-k2p7-code` passed `2/2` at an estimated `$0.00027790`.

## Operational Policy

- Use local Gemma first when an AMD pod endpoint is available and validated.
- In Fireworks-only mode, the Docker image now enables `FIREWORKS_MATRIX_WEIGHTS=/app/router/data/fireworks_track1_allowed_weights.json` by default.
- The checked-in matrix weights now use `76` completed, deduplicated, observed Track 1 rows from category, hidden-variant, and championship result files.
- Transport/access failures such as Gemma `404` are excluded from quality fitting by default. The weights record `observed_models`, and the matrix selector filters unobserved allowed models when observed alternatives exist.
- The matrix selector uses ridge-regression utility plus Nash welfare. For strong tasks, regression/accuracy is weighted above token cost; for cheap tasks, token cost remains a larger part of the score.
- Keep `minimax-m3` as the preferred remote candidate for observed Track 1 domains because it matched or exceeded the accessible alternatives at lower estimated token cost after the championship recalibration.
- Keep `kimi-k2p7-code` as an observed fallback for code/debug cases if Minimax errors at runtime.
- Keep Gemma IDs in `ALLOWED_MODELS` support, but cache unavailable-model errors per runner instance so one inaccessible Gemma endpoint does not cause repeated latency across the whole evaluator batch.

## Classifier Hardening

The pre-routing classifier now treats common hidden-evaluator variants as their semantic domain before applying Pareto/Nash scoring:

- direct arithmetic prompts such as `Compute 17 * 6 + 4` map to `math_reasoning` instead of `formatting`;
- numeric JSON prompts such as `Given values [...], return min and max` map to `math_reasoning` even when they request minified JSON;
- `Fix this Python code...` maps to `code_debug`, preserving the calibrated Kimi preference;
- `Write a Python function...` maps to `code_generation`, preserving the calibrated Minimax preference.
- quantified logic prompts such as `All merls are... Is it guaranteed... Return exactly yes or no` map to `logic` instead of `formatting`.

This does not answer tasks by regex. It only prevents format words like `Return only` or `JSON` from polluting the model-selection feature vector.

## Follow-Up Calibration

- Re-run this benchmark if the official page, Participant Guide, or Discord announces a model-access change.
- If Gemma becomes available through Fireworks serverless, repeat this run and fit `FIREWORKS_MATRIX_WEIGHTS` from the new result file.
- If local Gemma is served from AMD pod, compare `ROUTER_MODE=hybrid` against `ROUTER_MODE=fireworks` on the same dataset and rank by accuracy first, then Fireworks token count.
