# E2B 2,000-Task Regression Protocol

## Question

Can the calibrated FunctionGemma intent and five ordinal task scores identify a task region where the text-only Gemma E2B produces sufficiently accurate answers at a 96-output-token ceiling?

## Frozen Corpus

- 2,000 unseen synthetic tasks, balanced at 250 tasks for each Track 1 category.
- Original split: 1,429 train, 284 validation and 287 locked-test tasks.
- Valid FunctionGemma subset: 1,422 train, 283 validation and 286 locked-test tasks. The nine malformed assessments fail closed to Fireworks and never become silently repaired regression rows.
- Mutation lineages and template families never cross splits.
- FunctionGemma sees only the untouched task and emits one `assess_task` call.
- E2B sees only the untouched user task, with temperature 0 and a 96-token ceiling.

## Fail-Closed Accounting

A malformed FunctionGemma call is an observed router failure. It is counted in the end-to-end architecture report and routes to Fireworks. It is not relabeled from teacher metadata and cannot enter E2B regression, because E2B would not be eligible at runtime without a valid assessment.

E2B runtime failures remain matrix rows with explicit failure state. Judge disagreements remain missing binary outcomes rather than being silently converted to errors or successes.

## Correctness Labels

Every valid E2B candidate is independently judged by:

- `accounts/fireworks/models/kimi-k2p7-code`;
- `Gemini 3.5 Flash (Medium)` through the pinned Antigravity account.

Only unanimous correct or unanimous incorrect judgments become binary regression labels. Uncertain or conflicting judgments remain explicit disagreements.

An initial Minimax judging pilot is retained as auxiliary provenance but excluded from the pinned consensus policy: its structured throughput was too low for the 1,991-row matrix. Kimi is independent of the Gemma candidate, supports the same strict judge contract and completed the exact-runtime cross-judge baseline at materially higher throughput.

## Matrix Regression

Candidate models are a smoothed constant, logistic linear regression and logistic regression with predeclared squared and interaction terms. Selection follows this order:

1. Fit every candidate on train only.
2. Select on validation Brier score, preferring the simpler model within the fixed tolerance.
3. Refit only the selected formula on train plus validation.
4. Evaluate once on locked test; never use locked-test results to choose features or model form.

Held-out probabilities are grouped into at most five equal-frequency calibration bins. Runtime feasibility uses each bin's 95% Wilson lower confidence bound rather than its mean predicted accuracy. This prevents a small or overconfident region from clearing the accuracy gate on point estimates alone.

Latency and token outcomes compare a constant against ridge regression over `log1p` targets under the same split discipline.

## Learning Curve And Expansion

The initial 2,000-task experiment is a decision point, not an automatic invitation to generate arbitrary volume. `analyze_regression_learning_curve.py` fits nested train subsets at 100, 250, 500, 1,000 and full size, repeats non-full samples under deterministic lineage ordering, and evaluates only on validation. Locked-test outcomes never influence model selection or the decision to expand.

If the validation Brier curve has not plateaued, additional examples should be lineage-diverse. If it has plateaued, broad random generation stops and the next dataset targets:

- probability regions near the routing threshold;
- intents with poor calibration or sparse safe-local coverage;
- FunctionGemma boundary inversions;
- E2B failures, teacher disagreements and output-degeneration cases.

The five FunctionGemma scores and structural input features remain pre-generation routing signals. Candidate-answer properties cannot enter that regression because they do not exist when the engine is selected.

## Post-Generation Rescue Gate

The local answer passes through a separate mechanical gate before release. Safe formatting-only defects are normalized locally when the repaired answer passes the strict validator again. This includes extractable JSON, unambiguous yes/no, valid code surrounded by prose and removable Markdown fences. Numeric prose is never converted by taking its first number. Remaining high-confidence corruption such as empty output, invalid strict formats, syntactically invalid requested Python, unclosed Markdown fences and repeated-generation loops escalates. Natural lists or free text are not rejected merely for lacking terminal punctuation.

`audit_e2b_rescue_gate.py` compares this gate with the two-teacher consensus and reports:

- incorrect local answers rescued by escalation;
- correct local answers escalated unnecessarily;
- released-answer precision;
- rejection reasons and outcomes by intent.

A rejected E2B answer falls back to Fireworks. This gate is not a second LLM validator and consumes zero Fireworks tokens unless it actually escalates.

## Promotion Rule

E2B remains disabled unless all conditions hold:

- locked-test evidence predicts a non-empty task region above the configured accuracy gate after uncertainty;
- the result materially improves over the constant prior and survives category-level review;
- combined FunctionGemma plus E2B memory remains below the final 4 GB Docker limit;
- the exact `linux/amd64` image completes the official-style batch inside ten minutes;
- malformed assessment, local timeout, recoverable OOM and invalid answer paths fall closed to Fireworks.

If the five scores do not predict E2B correctness, the valid result is to keep E2B disabled. The experiment is designed to discover a safe advantage, not to force one.

## Final Result

The frozen run produced 1,991 valid candidates, 1,323 unanimous binary outcomes and 668 disagreements. The nonlinear logistic challenger reached a validation learning-curve plateau, but its locked-test selected region achieved only `45/88` correct (`51.14%`) with a 95% Wilson lower bound of `40.87%`. This fails the `60%` promotion gate. E2B remains disabled in the championship policy, and the 2,000-task coefficients replace the earlier 93-task prior only as calibrated negative evidence.
