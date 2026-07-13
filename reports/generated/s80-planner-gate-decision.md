# Sprint 80 Planner Gate Decision

## Decision

**Do not promote or broaden the planner gate.** No production routing file was changed.

The planner remains valuable for the four purpose-built tool families in its dedicated distribution. On the AMD replay it released **1,393/1,393 correct answers** with zero unsafe false positives. That result does not transfer to the broad Track 1 population because the available executor does not implement most of the required operations.

## Broad Population Result

| Metric | Result |
|---|---:|
| Reconciled population | 4,400 |
| Structural-prefilter matches | 81 |
| Matches still eligible after the existing deterministic solver | 71 |
| Valid planner releases | 0 |
| Correct planner releases | 0 |
| Mean planner latency on the 71 runtime candidates | 524.29 ms |

The production ordering matters: `solve_deterministic` runs before the planner. Ten of the 81 apparent planner candidates were already resolved mechanically and would never reach the planner. Among the remaining 71, the frozen planner produced 20 safe declines, 14 provenance/value rejections, 18 missing-argument/key rejections, and 19 malformed-call exceptions.

## Protected Evidence

The protected holdout contained 23 post-solver planner candidates:

| Outcome | Count |
|---|---:|
| Valid releases | 0 |
| Safe declines | 7 |
| Rejected plans | 8 |
| Parse exceptions | 8 |

There is therefore no protected positive cohort from which to estimate released-answer precision, Wilson bounds, or a safe admission threshold. A learned gate cannot turn rejected plans into answers; it can only avoid unnecessary planner calls.

## Why Broad Retraining Is Not A Championship Gain

The broad tasks that triggered the lexical prefilter mostly require unsupported capabilities: geometry, recurrences, matrices, conditional sentiment rules, constrained code generation, second-place ordering, or multi-entity state transitions. Simple explicit arithmetic and endpoint ordering are generally captured by the existing deterministic solvers before the planner.

Training the planner on the 4,400 broad rows as `decline_tool` examples could reduce malformed calls and approximately 0.5 seconds of local latency per false admission. It would not create a validated local answer, avoid a Fireworks call, or improve accuracy. Positive retraining would first require new allowlisted executors, provenance validators, proof recomputation, answer rendering, and protected examples for those new families.

## Safe Championship Action

- Keep the current narrow planner prefilter and fail-closed proof chain.
- Do not broaden admission from FunctionGemma scores alone.
- Do not retrain on sealed outcomes or synthesize positive labels unsupported by an executable proof.
- Spend the remaining optimization window on Fireworks answer quality and the already labeled E2B selection problem, where measurable accuracy and token gains exist.

## Reproducibility

- Broad planner replay: `/tmp/s80-full-pop-planner-4400.jsonl`
- Broad summary: `/tmp/s80-full-pop-planner-summary.json`
- Authoritative population: `evals/router-ml-v3/ledger.jsonl`
- Prompt/reference join: `scripts/run_e2b_contract_population.py`
- Runtime eligibility: `is_tool_planner_candidate(prompt) and solve_deterministic(task) is None`

