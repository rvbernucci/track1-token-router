# Sprint 68 - Answer Contract Adversarial Fuzzing

## Objective

Attack Answer Contract Engine with malformed, ambiguous and adversarial responses while proving it never changes semantic content or releases an invalid official result.

## Corpus

- [x] Build 2,000 deterministic fuzz cases from seed `68068`.
- [x] Cover JSON, numbers, booleans, labels, lists, NER, summaries and code: 250 each.
- [x] Include Markdown fences, prefixes, suffixes, duplicate answers and truncation.
- [x] Include conflicting instructions, nested quoting and prompt injection.
- [x] Include RTL markers, emoji, null bytes and unusual whitespace without normalizing identifiers.
- [x] Include Python, JavaScript and TypeScript code with explanations and unsafe imports.
- [x] Tag every mutation with an expected `accept`, `repair` or `reject` outcome.

## Properties

- [x] Safe repairs are deterministic and idempotent.
- [x] Repair never invents missing semantic content.
- [x] Ambiguous numeric, boolean and label candidates are rejected.
- [x] JSON repair never changes keys or values.
- [x] Code extraction preserves executable semantics and language.
- [x] NER normalization does not silently alter entity values.
- [x] Unicode/RTL content is preserved rather than normalized into another identifier.
- [x] Final serialization always emits exactly `task_id` and `answer`.

## Execution

- [x] Run seeded property-based generation with reproducible manifest hash `d9d71ec2863495b92556c5c82a515773ff8dae628fc0995ac19f90114efec338`.
- [x] Exercise nine repair actions and ten rejection reasons.
- [x] Differentially compare pre-contract and post-contract semantic validators.
- [x] Minimize the three discovered defects into compact regression fixtures.
- [x] Add negated boolean, unsafe import and natural fenced-code cases to permanent tests.
- [x] Run the repository secret/log redaction gate over the final corpus.

## Gates

- [x] Zero semantic mutations among accepted repairs.
- [x] Zero false acceptance of ambiguous candidates.
- [x] `100%` idempotence for valid and repaired answers.
- [x] `100%` official JSON serialization validity.
- [x] Zero crashes across 2,000 cases.
- [x] Every discovered defect has a minimized regression test.
- [x] Fuzz run is reproducible from seed and manifest hash.

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

Status: **complete and promoted**.

The first run exposed three minimized defects: negated yes/no acceptance, unsafe Python imports, and missed natural fenced-code contracts. After fail-closed fixes, all 2,000 cases passed: 541 accepts, 773 safe repairs and 686 rejects, with zero semantic mutations, false accepts, crashes, idempotence failures or serialization failures. The permanent fixtures are in `evals/answer-contract-fuzz-v2/regressions.jsonl`.
