# Battle Drill Report

- tasks: 160
- candidate_policy: `balanced`
- candidate_score: `886.925`
- exact_match_rate: `1.0`
- remote_tokens_total: `5600`
- remote_packet_tokens: `1075`

## Scoreboard

| rank | policy | score | exact_match_rate | remote_tokens | packet_tokens | budget_violations |
|---:|---|---:|---:|---:|---:|---:|
| 1 | balanced | 886.925 | 1.000 | 5600 | 1075 | 0 |
| 2 | aggressive | 750.000 | 0.750 | 0 | 0 | 0 |
| 3 | conservative | 498.274 | 1.000 | 22400 | 3726 | 1 |

## Adaptive Policy Ablation

| rank | profile | expected_route_match_rate | actions |
|---:|---|---:|---|
| 1 | adaptive_aggressive | 1.000 | `{"approve": 80, "remote_audit": 20, "repair": 60}` |
| 2 | adaptive_balanced | 1.000 | `{"approve": 80, "remote_audit": 20, "repair": 60}` |
| 3 | adaptive_conservative | 1.000 | `{"approve": 80, "remote_audit": 20, "repair": 60}` |

## Competition Mode Probe

| input | route | action | remote_would_call | repaired |
|---|---|---|---:|---:|
| What is 10 + 5? Return only the number. | guardrail_arithmetic | approve | False | False |
| What is 6 * 7? Return only the number. | solver_arithmetic | approve | False | False |
| Return exactly SAFE_OUTPUT and nothing else. | guardrail_echo | approve | False | False |
| Who is the CEO of AMD today? | m2b_fireworks_approved | remote_audit | True | False |

## Solver Pack

- solved: `3`
- blocked: `2`
- saved_cascade_calls: `3`

## Fuzz Pack

- contract_success: `True`
- exact_match_rate: `1.0`
- classes: `15`

## Readiness

- candidate_selected: `ok`
- candidate_has_full_accuracy: `ok`
- budget_clean: `ok`
- prompt_manifest_clean: `ok`
- trace_fixture_loaded: `ok`
- guardrails_probe_safe: `ok`
- competition_mode_ready: `ok`
- solver_pack_ready: `ok`
- fuzz_pack_ready: `ok`

## Risks

- Trace fixture contains error routes; keep fallbacks visible.
- Best offline policy still spends remote tokens; calibrate with real Fireworks pricing.
