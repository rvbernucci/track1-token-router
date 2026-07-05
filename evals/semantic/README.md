# Semantic Eval

This offline harness is a deterministic risk sensor for open-ended answers.

It does not replace official scoring and it is not an LLM judge. It uses stable rubrics with required keywords, forbidden patterns, format constraints, word limits and escalation requirements.

## Files

- `tasks.jsonl`: semantic tasks grouped by category.
- `rubrics.jsonl`: deterministic rubrics and fixture candidate answers.

## Labels

- `acceptable`: answer satisfies the rubric.
- `partial`: answer contains some useful signal but misses required coverage.
- `format_fail`: answer violates a requested strict format.
- `unsafe`: answer exposes or follows unsafe instructions.
- `hallucinated`: answer makes a forbidden or unstable claim.
- `too_verbose`: answer exceeds the word budget.

## Run

```bash
python3 scripts/run_semantic_eval.py --check --report reports/generated/semantic-eval.md
```

Optional external answers can be passed as JSONL:

```bash
python3 scripts/run_semantic_eval.py --answers path/to/answers.jsonl
```

The answers file must contain `id` and `answer` fields.
