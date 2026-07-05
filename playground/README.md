# Playground

Manual experiments live here.

This is the Python equivalent of a quick TypeScript `test.ts`, but with guardrails:

- keep experiments deterministic;
- do not require real credits;
- print useful inspection output;
- promote useful experiments into `tests/`.

## Examples

```bash
python3 playground/test_policy_logic.py
python3 playground/test_adapter_logic.py
python3 playground/test_prompt_packets.py
```

## Promotion Rule

Move playground logic into `tests/` when it protects behavior we care about during the hackathon.
