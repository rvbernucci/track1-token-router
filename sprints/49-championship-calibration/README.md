# Sprint 49 - Championship Calibration

## Objective

Select the final Docker image using accuracy-matched Fireworks token efficiency and prove whether the assessment/regression/game-theory architecture adds value.

## Ablation Variants

- Fireworks-only champion.
- Static deterministic plus Fireworks.
- Direct FunctionGemma three-way classifier baseline.
- Assessment plus linear expected-utility selector.
- Assessment plus accuracy gate and minimax regret.
- Full system with E2B and Fireworks Pareto/Nash selection.

## Checklist

- [x] Freeze hidden and adversarial evaluation sets before tuning.
- [x] Run every variant on identical tasks and runtime constraints.
- [x] Measure end-to-end answer accuracy before token ranking.
- [x] Measure assessment calibration and decision regret.
- [x] Measure Fireworks input/output tokens by intent and engine.
- [ ] Measure final-image cold start, peak RSS and total runtime; provider p50/p95 is already recorded.
- [x] Bootstrap close differences by mutation lineage and report confidence intervals.
- [x] Stress distribution shift by perturbing all five score dimensions.
- [x] Refit utility weights only on validation data.
- [ ] Test the exact public Linux `amd64` image under 4 GB/2 vCPU.
- [ ] Run secret, manifest, size and pullability audits.
- [ ] Freeze model, dataset, rubric, matrices, image and commit revisions.
- [x] Promote one runtime policy and document every rejected variant.

## Promotion Order

1. Eliminate variants below the accuracy gate.
2. Eliminate variants that violate memory, runtime or delivery constraints.
3. Rank survivors by Fireworks tokens.
4. Use latency and operational simplicity as tie-breakers.

## Gate

The selected system is no worse than the accuracy-matched champion, consumes fewer Fireworks tokens, remains robust to assessment error and satisfies every official container constraint.

## Frozen Policy Result

Validation selected `deterministic_then_kimi` among promotion-eligible variants. On the 287-task locked test it achieved `171/287` conservative correctness, `75.0%` binary accuracy and `73,870` Fireworks tokens.

Rejected variants:

- E2B challenger: `54.70%`, `57,103` tokens; paired lineage bootstrap accuracy delta versus champion `[-7.77, -2.08]` percentage points;
- per-intent candidate: `56.10%`, `81,474` tokens;
- matrix plus Pareto/Nash: `57.84%`, `78,853` tokens;
- Minimax-only: `50.52%`, `101,447` tokens.

The current deterministic registry refused all 571 broad frozen tasks, so it was accuracy/token equivalent to Kimi-only. It remains promoted because exact registered acceptance can save tokens on unseen mechanical tasks and every refusal preserves the Kimi baseline.

Public reproducibility:

- evidence pack: `data/championship-ablation/manifest.json`;
- ablation: `reports/public/championship-ablation.md`;
- score-shift stress: `reports/public/score-shift-stress.md`;
- command: `python3 scripts/championship_ablation.py`.
