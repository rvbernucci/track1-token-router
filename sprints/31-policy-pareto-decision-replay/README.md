# Sprint 31 - Policy Pareto & Decision Replay

## Type

Does not depend on credit.

## Objective

Create offline tools to explore the Pareto frontier of routing policies and generate readable replays of individual decisions.

## Why It Matters

The project needs to justify why the default policy is good. Moreover, the demo and the pitch become much stronger when we can show a real decision step-by-step.

## Thesis

The best technical argument is not "we have a cascade". It is "this decision saved tokens without sacrificing format, budget, or confidence".

## Deliverables

- `scripts/optimize_policy.py`.
- `scripts/replay_decision.py`.
- `reports/generated/policy-pareto.md`.
- `reports/generated/decision-replay.md`.
- Recommended default profile and justification.
- Update of the video script with real examples.
- Replay and optimizer tests.

## Checklist

- [x] Sweep `repair_threshold`.
- [x] Sweep `remote_threshold`.
- [x] Sweep `low_budget_deny_threshold`.
- [x] Compare exact-match proxy.
- [x] Compare estimated packet tokens.
- [x] Compare escalation rate.
- [x] Compare budget violations.
- [x] Generate Pareto table.
- [x] Mark dominated policies.
- [x] Suggest default profile.
- [x] Create `replay_decision.py --text`.
- [x] Replay shows guardrail/solver.
- [x] Replay shows risk signals.
- [x] Replay shows budget decision.
- [x] Replay shows policy decision.
- [x] Replay shows final validator.
- [x] Replay shows final response.
- [x] Update `submission/video-script.md` with real examples.

## Acceptance Criteria

- `optimize_policy.py` runs without a real model.
- Pareto report differentiates dominated and candidate policies.
- `replay_decision.py` generates Markdown useful for a demo.
- The default profile remains documented as a decision, not a guess.
- The video script gains at least two concrete examples.

## Metrics

- Exact match proxy per profile.
- Remote packet tokens per profile.
- Escalation rate per profile.
- Budget violations per profile.
- Number of dominated policies.

## Expected Commands

```bash
python3 scripts/optimize_policy.py --report reports/generated/policy-pareto.md
python3 scripts/replay_decision.py --text "What is 6 * 7? Return only the number." --report reports/generated/decision-replay.md
```

## Risks

- Over-optimizing for the offline dataset.
- Confusing the exact match proxy with official scoring.
- Choosing a profile that is too aggressive for apparent savings.

## Decision

The optimizer informs, but does not replace human judgment. The final policy must consider accuracy, token exposure, latency, and robustness against unknown formats.

## Definition of Done

- Pareto report exists.
- Decision replay exists.
- Default profile has a justification.
- Video script references real replays.
- Battle drill remains the main gatekeeper.

## Evidence

- `docs/EVALUATOR_ASSUMPTIONS.md` documents hypotheses, impact, mitigation, tests, and kickoff questions.
- `docs/KICKOFF_ADAPTER_DRILL.md` defines the adaptation procedure in under 30 minutes.
- `fixtures/adapter-drill/` contains `scoring_text_batch`, `scoring_json_envelope`, and `scoring_file_bundle`.
- `router/adapters/official/` contains experimental adapters for the three formats.
- `scripts/adapter_drill.py --check` generates `reports/generated/adapter-drill-report.md`.
- `tests/test_official_adapters.py` covers parse and format of the three formats.
- `scripts/offline_release_check.sh` runs the drill before the battle drill.
