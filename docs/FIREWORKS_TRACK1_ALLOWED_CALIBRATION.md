# Fireworks Track 1 Allowed Models Calibration

Last run: 2026-07-09

Dataset: `evals/fireworks-pareto/track1-category-microbench.jsonl`

Command shape:

```bash
python3 scripts/fireworks_microbench.py \
  --dataset evals/fireworks-pareto/track1-category-microbench.jsonl \
  --models "minimax-m3,kimi-k2p7-code,gemma-4-31b-it,gemma-4-26b-a4b-it,gemma-4-31b-it-nvfp4" \
  --max-calls 80 \
  --budget-usd 0.05 \
  --max-tokens 96
```

Actual estimated spend: `$0.00447050`.

## Aggregate Results

| Model | Valid | Calls | Error Calls | Tokens | Estimated Cost USD | Avg Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `accounts/fireworks/models/minimax-m3` | 15 | 16 | 0 | 3148 | 0.00138990 | 1654 |
| `accounts/fireworks/models/kimi-k2p7-code` | 14 | 16 | 0 | 1554 | 0.00308060 | 1599 |
| `accounts/fireworks/models/gemma-4-31b-it` | 0 | 16 | 16 | 0 | 0.00000000 | 560 |
| `accounts/fireworks/models/gemma-4-26b-a4b-it` | 0 | 16 | 16 | 0 | 0.00000000 | 547 |
| `accounts/fireworks/models/gemma-4-31b-it-nvfp4` | 0 | 16 | 16 | 0 | 0.00000000 | 487 |

## Observations

- `minimax-m3` is the current safest Fireworks fallback among accessible Track 1 allowed models.
- `kimi-k2p7-code` is viable, but it cost more in this run and failed one code debugging task due to truncated/invalid code.
- The three Gemma serverless IDs returned `HTTP 404 Not Found` with the current local Fireworks key.
- Gemma should remain in the architecture through AMD local inference and should still be attempted when the official harness exposes it, but repeated 404s should be cached and skipped within a batch.
- NER data/date/currency tasks need explicit formatting instructions in our evals; otherwise semantic normalization can look like a mechanical failure.

After tightening the `ner_money_date` prompt to require date and amount exactly as shown in the source text, a two-call retest with `minimax-m3` and `kimi-k2p7-code` passed `2/2` at an estimated `$0.00027790`.

## Operational Policy

- Use local Gemma first when an AMD pod endpoint is available and validated.
- In Fireworks-only mode, keep `minimax-m3` as the conservative default for strong reasoning, code, logic, math, summarization, and factual tasks.
- Keep `kimi-k2p7-code` as a fallback/candidate, especially for code tasks where future calibration may show stronger behavior.
- Keep Gemma IDs in `ALLOWED_MODELS` support, but cache unavailable-model errors per runner instance so one inaccessible Gemma endpoint does not cause repeated latency across the whole evaluator batch.

## Follow-Up Calibration

- Re-run this benchmark if the official page, Participant Guide, or Discord announces a model-access change.
- If Gemma becomes available through Fireworks serverless, repeat this run and fit `FIREWORKS_MATRIX_WEIGHTS` from the new result file.
- If local Gemma is served from AMD pod, compare `ROUTER_MODE=hybrid` against `ROUTER_MODE=fireworks` on the same dataset and rank by accuracy first, then Fireworks token count.
