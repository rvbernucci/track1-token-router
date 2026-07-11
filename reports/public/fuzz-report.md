# Fuzz Eval Report

- tasks: 16
- contract_success: `True`
- traces_complete: `True`
- exact_match_rate: `1.0`
- final_answer_repaired: `1`
- remote_would_call: `0`
- routes: `{"guardrail_arithmetic": 2, "guardrail_echo": 4, "guardrail_empty": 2, "guardrail_greeting": 1, "m1_approved": 4, "m2b_candidate": 1, "solver_json_transform": 2}`

## Classes

| class | tasks | exact_match_rate | routes |
|---|---:|---:|---|
| empty | 1 | 1.0 | `{"guardrail_empty": 1}` |
| file_json | 1 | 1.0 | `{"guardrail_echo": 1}` |
| file_txt | 1 | 1.0 | `{"guardrail_echo": 1}` |
| json_alt_field | 2 | 1.0 | `{"guardrail_arithmetic": 1, "guardrail_echo": 1}` |
| json_compact | 1 | 1.0 | `{"solver_json_transform": 1}` |
| large_payload | 1 | None | `{"m1_approved": 1}` |
| literal_echo | 1 | 1.0 | `{"guardrail_echo": 1}` |
| malformed_json_like | 1 | None | `{"m1_approved": 1}` |
| markdown_forbidden | 1 | 1.0 | `{"solver_json_transform": 1}` |
| multiline | 1 | None | `{"m1_approved": 1}` |
| number_only | 1 | 1.0 | `{"guardrail_arithmetic": 1}` |
| prompt_injection | 1 | None | `{"m2b_candidate": 1}` |
| unicode | 1 | 1.0 | `{"guardrail_greeting": 1}` |
| uppercase | 1 | None | `{"m1_approved": 1}` |
| whitespace | 1 | 1.0 | `{"guardrail_empty": 1}` |
