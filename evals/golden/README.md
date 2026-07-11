# Golden Eval Set

Initial dataset to calibrate the router before the kickoff.

It is not intended to represent the official scoring. It serves to measure local regression, route distribution, remote tokens, and behavior in easy, medium, hard, and adversarial tasks.

## Files

- `tasks.jsonl`: input tasks.
- `expected.jsonl`: expected responses for simple exact matches.

## Usage

```bash
python3 -m router eval \
  --jsonl evals/golden/tasks.jsonl \
  --expected evals/golden/expected.jsonl \
  --out reports/generated/golden-output.jsonl \
  --report reports/generated/golden-report.md
```

