# Fireworks Track 1 Allowed Models Calibration

Updated: 2026-07-11

## Final Promotion

The `default_enabled=false` policy below is historical Sprint 49 evidence. Sprint 63 ran a new paired 46-call benchmark under the final raw-prompt protocol and 96-token ceiling. The promoted `configs/fireworks-intent-policy-v2.json` uses Kimi by default and MiniMax for NER/extraction. It matched the strongest result at 21/23 valid answers while reducing scored tokens from 3,869 to 1,967. Estimated experiment spend was `$0.00370335`; paired token-savings CI95 was `[1,608, 2,185]`.

The policy SHA-256 is `b57498d17e9d560e9990b56492e5b5aa51d0ce8ac060c83a2f56a4f847b4792a`. It remains subordinate to runtime `ALLOWED_MODELS`. See `reports/public/final-pareto-calibration.md` for current evidence.

## Historical Sprint 49 Evidence

## Championship Runtime Finding

On the frozen validation/test corpus, omitting `reasoning_effort` for strong Minimax M3 tasks produced repeated OpenAI-compatible responses without usable `message.content`. The same model completed the earlier 571-task run without this failure when `reasoning_effort="none"` was present. The router therefore sends `none` for Minimax and Kimi in every tier, while Gemma continues to omit the unsupported field. The historical exact-runtime `v4` baseline used `M1_SYSTEM_PROMPT`; it is retained as evidence but is not directly comparable with the current `raw-prompt-v1` runtime.

The exact-runtime baseline uses cross-model judging: Kimi judges Minimax candidates, Minimax judges Kimi candidates, and Gemini 3.5 Flash Medium independently judges both sets. A model never judges its own answer. Only unanimous decisions become binary outcomes; disagreement remains conservatively not correct for policy comparison. Claude Sonnet 5 rows collected during a slow subscription-CLI pilot are retained as auxiliary provenance but are not members of the pinned baseline judge policy.

The competition selector now treats Fireworks tokens, not API dollar price, as the scarce-resource player. Capability and a 95% Wilson empirical accuracy lower bound form hard feasibility gates; Nash welfare, Pareto dominance and the matrix target optimize token count only among feasible models. Dollar price remains visible in traces and acts only after accuracy and token ties.

## Frozen 571-Task Baseline

The larger historical exact-runtime experiment evaluates the frozen validation and locked-test portions of the 2,000-task corpus. Both candidates received the same user task, legacy `M1_SYSTEM_PROMPT`, temperature, dynamic token cap, `reasoning_effort="none"` and request metadata. New promotion evidence must use `raw-prompt-v1`, where the answer model receives only the user prompt.

The 240-task concise-system ablation rejected an additional brevity prompt. It preserved 75% accuracy but increased total Fireworks tokens by 33.5%, adding 5,520 prompt tokens while saving only eight completion tokens. Output brevity must therefore come from the original task, dynamic completion ceilings, validated structured decoding, and local Answer Contract normalization rather than a global system instruction.

| Model | Answered | Fireworks tokens | Validation conservative accuracy | Locked-test conservative accuracy | Locked-test avg tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| `kimi-k2p7-code` | 571/571 | 147,695 | 58.45% | 59.58% | 257.4 |
| `minimax-m3` | 570/571 | 202,913 | 56.69% | 50.52% | 353.5 |

The single Minimax runtime failure is retained rather than retried away. Two independent non-self judges evaluate each answered candidate. Unanimous judgments are binary; disagreement counts as incorrect in conservative promotion metrics.

Per-intent selection was frozen on validation. It selected Minimax for `logic_puzzle` and `sentiment`, and Kimi for the other six intents. On the locked test that candidate achieved `56.10%` conservative accuracy, a `50.31%` Wilson lower bound, and `81,474` tokens over 287 tasks. It failed the predeclared `60%` promotion gate. The candidate therefore remains `default_enabled=false`; the locked test did not trigger any post-hoc intent reselection.

Authoritative artifacts:

- comparison: `reports/generated/e2b-2000-baselines/fireworks-baseline-comparison.json`;
- human report: `reports/generated/e2b-2000-baselines/fireworks-baseline-comparison.md`;
- candidate runtime policy: `configs/fireworks-intent-policy-v1.json`;
- policy SHA-256: `f10e31382bb39378834b9ec76c1d11b5b9c6e3e17f5d9bc782909004c8344c91`.

Last run: 2026-07-09

Primary dataset: `evals/fireworks-pareto/track1-category-microbench.jsonl`

Hidden-variant dataset: `evals/fireworks-pareto/hidden-variant-microbench.jsonl`

Frontier dataset: `evals/fireworks-pareto/frontier-microbench.jsonl`

Structure-heldout dataset: `evals/fireworks-pareto/structure-heldout-microbench.jsonl`

Adversarial hidden dataset: `evals/fireworks-pareto/adversarial-hidden-microbench.jsonl`

Escape dataset: `evals/fireworks-pareto/escape-microbench.jsonl`

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

Latest frontier result file: `reports/generated/fireworks-frontier-20260709-results.jsonl`

Latest primary report: `reports/generated/fireworks-track1-category-20260709-report.md`

Latest hidden-variant report: `reports/generated/fireworks-hidden-variant-report.md`

Latest frontier report: `reports/generated/fireworks-frontier-20260709-report.md`

Latest structure-heldout result file: `reports/generated/fireworks-structure-heldout-20260709-results.jsonl`

Latest structure-heldout report: `reports/generated/fireworks-structure-heldout-20260709-report.md`

Latest escape result file: `reports/generated/fireworks-escape-20260709-results.jsonl`

Latest escape report: `reports/generated/fireworks-escape-20260709-report.md`

Latest runtime-router escape result file: `reports/generated/fireworks-runtime-escape-20260709-after-math-results.jsonl`

Latest runtime-router escape report: `reports/generated/fireworks-runtime-escape-20260709-after-math-report.md`

Latest expanded runtime-router result file: `reports/generated/fireworks-runtime-frontier-structure-hidden-20260709-literal-zero-results.jsonl`

Latest expanded runtime-router report: `reports/generated/fireworks-runtime-frontier-structure-hidden-20260709-literal-zero-report.md`

Latest adversarial zero-token runtime result file: `reports/generated/fireworks-runtime-zero-token-111-results.jsonl`

Latest adversarial zero-token runtime report: `reports/generated/fireworks-runtime-zero-token-111-report.md`

Actual estimated spend for primary + hidden + championship + frontier + structure-heldout + escape: `$0.05761872`.

Total aggregated historical result spend in the leaderboard is `$0.05761872`.

Additional runtime-router eval spend across three iterative escape runs: `$0.00517975`.

## Aggregate Results

| Model | Valid | Calls | Error Calls | Tokens | Estimated Cost USD | Avg Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `accounts/fireworks/models/kimi-k2p7-code` | 90 | 96 | 0 | 9629 | 0.01981950 | 2204 |
| `accounts/fireworks/models/minimax-m3` | 90 | 96 | 3 | 18143 | 0.00798720 | 1613 |
| `accounts/fireworks/models/gemma-4-31b-it` | 0 | 64 | 64 | 0 | 0.00000000 | 380 |
| `accounts/fireworks/models/gemma-4-26b-a4b-it` | 0 | 64 | 64 | 0 | 0.00000000 | 371 |
| `accounts/fireworks/models/gemma-4-31b-it-nvfp4` | 0 | 64 | 64 | 0 | 0.00000000 | 372 |

## Historical Microbench Observations

- `minimax-m3` was cheaper in development dollars on the initial microbench, but Track 1 scores tokens rather than USD and the larger exact-runtime baseline now favors Kimi globally.
- Escape rerun with 80 focused calls cost `$0.00557805`; `minimax-m3` passed `16/16`, while `kimi-k2p7-code` passed `14/16` with fewer tokens but failed two code tasks under strict output validation.
- Frontier rerun with 28 focused calls passed `27/28`; `kimi-k2p7-code` passed `14/14` with `1397` tokens, while `minimax-m3` passed `13/14` with `2846` tokens.
- Structure-heldout rerun with 120 calls cost `$0.00738105`; `kimi-k2p7-code` and `minimax-m3` both passed `21/24`, but Kimi used `2510` tokens versus Minimax `4398`.
- Domain policy changed again after escape calibration: `kimi-k2p7-code` is preferred where observed validity is comparable and domain/shape/model `usage.total` is materially lower, especially compact factual, summarization, logic and selected math probes; `minimax-m3` is now preferred for code generation/debug escapes, mixed sentiment, extraction robustness, and composed math where empirical risk outweighs token savings.
- Runtime-router escape eval after solver and token-budget hardening passed `16/16` tasks with `2065` Fireworks tokens, `7/16` zero-remote-token answers, no invalid Fireworks attempts, and estimated spend `$0.00147425`.
- Expanded runtime-router eval over `frontier + structure-heldout + hidden-variant` passed `46/46` tasks with `46/46` zero-remote-token answers after adding deterministic literal echo; this was verified against an unreachable fake Fireworks endpoint, proving no remote call was needed for that pack.
- Expanded runtime-router eval over six local Track 1 packs, including `adversarial-hidden`, passed `108/108` deduplicated tasks with `108/108` zero-remote-token answers, `fireworks_tasks=0`, `remote_tokens.total=0`, and estimated spend `$0.00`; this was verified against an unreachable fake Fireworks endpoint.
- Hidden-variant rerun: both accessible models passed `8/8`; `minimax-m3` cost `$0.00070650`, while `kimi-k2p7-code` cost `$0.00142610`.
- The three Gemma serverless IDs returned `HTTP 404 Not Found` with the current local Fireworks key.
- Gemma should remain in the architecture through AMD local inference and should still be attempted when the official harness exposes it, but repeated 404s should be cached and skipped within a batch.
- NER data/date/currency tasks need explicit formatting instructions in our evals; otherwise semantic normalization can look like a mechanical failure.

After tightening the `ner_money_date` prompt to require date and amount exactly as shown in the source text, a two-call retest with `minimax-m3` and `kimi-k2p7-code` passed `2/2` at an estimated `$0.00027790`.

## Operational Policy

- Use local Gemma first for AMD pod development/calibration when an endpoint is available and validated; do not assume Gemma 26B/31B fits the final `4 GB` RAM / `2 vCPU` grading container.
- In Fireworks-only mode, the Docker image promotes `FIREWORKS_CHAMPION_MODEL=accounts/fireworks/models/kimi-k2p7-code`; the preference applies only when Kimi is present in `ALLOWED_MODELS`.
- The matrix artifact remains bundled for fallback research and contingency ordering, but it cannot override the promoted champion. On the locked test it lost five conservative-correct answers and used 4,983 more tokens than Kimi.
- The old `v1` policy remains disabled. The final Docker image loads the SHA-pinned `v2` policy, which can select a preferred model only when that model appears in runtime `ALLOWED_MODELS`.
- If a future promoted policy selects a model absent from runtime `ALLOWED_MODELS`, the policy yields no model and the runner falls back to the matrix/Pareto/Nash ordering without making an invalid call.
- The checked-in matrix weights now use `183` completed, deduplicated, observed Track 1 rows from category, hidden-variant, championship, frontier, structure-heldout, and escape result files.
- Transport/access failures such as Gemma `404` are excluded from quality fitting by default. The weights record `observed_models`, and the matrix selector filters unobserved allowed models when observed alternatives exist.
- The matrix selector uses ridge-regression utility plus Nash welfare, predicted token-efficiency utility, and smoothed empirical validity by domain/shape/model because Track 1 ranks by Fireworks token count after the accuracy gate.
- The runtime token utility now blends static profile estimates with observed `avg_total_tokens` by domain/shape/model, weighted by sample confidence.
- Prefer `kimi-k2p7-code` when both observed models are valid and Kimi's predicted Fireworks token use is materially lower, especially compact factual QA, summarization, logic, selected math, and compact-formatting probes.
- Keep `minimax-m3` as the preferred remote fallback where empirical validity, extraction behavior, code generation/debug, mixed sentiment, composed math, or future hidden-evaluator data shows higher robustness than Kimi.
- Fireworks calls now use a dynamic completion budget under the global `FIREWORKS_MAX_TOKENS` ceiling: strict yes/no and numeric outputs get tiny caps, bounded JSON/summaries get medium caps, and code keeps a larger safety budget to avoid truncation-driven accuracy failures.
- Numeric completion caps are risk-aware: simple numeric outputs stay compact, while strong `math_reasoning` gets more headroom to avoid empty-content/truncation failures before final numeric emission.
- The `scripts/fireworks_runtime_eval.py` lab exercises the whole runtime path: deterministic solvers, matrix regression, Nash/Pareto selection, dynamic completion budgets, strict final validation and fallback attempts.
- Deterministic literal echo now handles explicit `Return exactly this string...` and single-token `Return exactly X and nothing else` requests before Fireworks, while avoiding `yes or no` logic prompts.
- In Fireworks-only mode, strict output validation now acts as an accuracy gate: if the selected model returns empty, invalid JSON, invalid number/yes-no, or irreparable Python/code output, the runner tries the next ranked candidate and records total tokens across attempts.
- Keep Gemma IDs in `ALLOWED_MODELS` support, but cache unavailable-model errors per runner instance so one inaccessible Gemma endpoint does not cause repeated latency across the whole evaluator batch.
- Keep LoRA/fine-tuned Fireworks deployments out of the default Track 1 runtime unless the official harness explicitly exposes them through `ALLOWED_MODELS`; see `docs/FIREWORKS_LORA_FINE_TUNING_STRATEGY.md`.

## Classifier Hardening

The pre-routing classifier now treats common hidden-evaluator variants as their semantic domain before applying Pareto/Nash scoring:

- direct arithmetic prompts such as `Compute 17 * 6 + 4` map to `math_reasoning` instead of `formatting`;
- numeric JSON prompts such as `Given values [...], return min and max` map to `math_reasoning` even when they request minified JSON;
- `Fix this Python code...` maps to `code_debug`, preserving the calibrated domain feature before observed-token scoring;
- `Write a Python function...` maps to `code_generation`, preserving the calibrated domain feature before observed-token scoring.
- quantified logic prompts such as `All merls are... Is it guaranteed... Return exactly yes or no` map to `logic` instead of `formatting`.
- contact extraction prompts such as `Extract name, email, and phone...` map to `extraction` instead of being polluted by phone-number arithmetic signals.

This does not answer tasks by regex. It only prevents format words like `Return only` or `JSON` from polluting the model-selection feature vector.

## Follow-Up Calibration

- Re-run this benchmark if the official page, Participant Guide, or Discord announces a model-access change.
- If Gemma becomes available through Fireworks serverless, repeat this run and fit `FIREWORKS_MATRIX_WEIGHTS` from the new result file.
- `ROUTER_MODE=three_route` is now the promoted runtime. The older selective E2B and `v1` intent-policy artifacts remain disabled; the final runtime uses the per-intent E2B matrix and `fireworks-intent-policy-v2.json`.
