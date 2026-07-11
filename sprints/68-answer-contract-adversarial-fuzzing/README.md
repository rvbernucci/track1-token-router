# Sprint 68 - Answer Contract Adversarial Fuzzing

## Objective

Attack Answer Contract Engine with malformed, ambiguous and adversarial responses while proving it never changes semantic content or releases an invalid official result.

## Corpus

- [ ] Build at least 2,000 deterministic fuzz cases.
- [ ] Cover JSON, numbers, booleans, labels, lists, NER, summaries and code.
- [ ] Include Markdown fences, prefixes, suffixes, duplicate answers and truncation.
- [ ] Include conflicting instructions, nested quoting and prompt injection.
- [ ] Include Unicode normalization, RTL markers, emoji, null bytes and unusual whitespace.
- [ ] Include Python, JavaScript and TypeScript code with explanations or unsafe imports.
- [ ] Tag every mutation with an expected `accept`, `repair` or `reject` outcome.

## Properties

- [ ] Safe repairs are deterministic and idempotent.
- [ ] Repair never invents missing semantic content.
- [ ] Ambiguous numeric or label candidates are rejected.
- [ ] JSON repair never changes keys or values.
- [ ] Code extraction preserves executable semantics and language.
- [ ] NER normalization does not silently alter entity values.
- [ ] Unicode normalization never merges distinct identifiers.
- [ ] Final serialization always emits exactly `task_id` and `answer`.

## Execution

- [ ] Run seeded property-based generation for reproducibility.
- [ ] Run mutation testing against every repair rule.
- [ ] Differentially compare pre-contract and post-contract semantic validators.
- [ ] Minimize every failing input to a compact regression fixture.
- [ ] Add each confirmed failure to the permanent unit-test corpus.
- [ ] Run secret/log redaction checks over all failures.

## Gates

- [ ] Zero semantic mutations among accepted repairs.
- [ ] Zero false acceptance of ambiguous candidates.
- [ ] `100%` idempotence for valid and repaired answers.
- [ ] `100%` official JSON serialization validity.
- [ ] Zero crashes across at least 2,000 cases.
- [ ] Every discovered defect has a minimized regression test.
- [ ] Fuzz run is reproducible from its seed and manifest hash.

## Evidence

- `evals/answer-contract-fuzz-v2/manifest.json`
- `evals/answer-contract-fuzz-v2/regressions.jsonl`
- `reports/generated/answer-contract-fuzz-v2/results.json`
- `reports/public/answer-contract-fuzz-v2.md`

## Command

```bash
python3 scripts/fuzz_answer_contract_v2.py \
  --cases 2000 --seed 68068 \
  --check --json
```

## Completion Decision

Any semantic mutation or ambiguous false acceptance blocks promotion. Safe coverage may expand only through a minimized fixture, mechanical proof and permanent regression test.
