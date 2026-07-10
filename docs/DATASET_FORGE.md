# Dataset Forge

The Dataset Forge creates reproducible FunctionGemma assessment data without manual chat copy/paste. It is dry-run by default and writes append-only JSONL plus atomic checkpoints.

## Providers

- Claude Code: exact model `claude-sonnet-5`, authenticated Claude Pro/Max only; API-key billing is rejected.
- Antigravity: exact model `Gemini 3.5 Flash (Medium)`, plan mode and sandbox; active account must match `DATASET_AGY_EXPECTED_EMAIL`.
- Fireworks: explicit fallback or independent rater only; every request reserves and reconciles an explicit USD budget.

Credentials never enter dataset rows. Provider provenance stores model, role, auth mode, token telemetry, request ID, configuration hash and billable Fireworks cost.

## Workflow

```bash
python3 scripts/dataset_forge.py plan --count 120 --seed 46
python3 scripts/dataset_forge.py --root data/dataset-forge/pilot generate \
  --count 120 --providers claude,agy --batch-size 10 --max-workers 2 --execute
python3 scripts/dataset_forge.py --root data/dataset-forge/pilot validate
python3 scripts/dataset_forge.py --root data/dataset-forge/pilot deduplicate
python3 scripts/dataset_forge.py --root data/dataset-forge/pilot rate-contract
python3 scripts/dataset_forge.py --root data/dataset-forge/pilot rate \
  --providers claude,agy --batch-size 10 --max-workers 2 --execute
python3 scripts/dataset_forge.py --root data/dataset-forge/pilot adjudicate
```

Only unresolved rows should receive a third independent rating:

```bash
python3 scripts/dataset_forge.py --root data/dataset-forge/pilot rate \
  --providers fireworks --scope needs-review --fireworks-budget-usd 0.10 --execute
python3 scripts/dataset_forge.py --root data/dataset-forge/pilot adjudicate
```

`rate-contract` records only facts already enforced by code: requested taxonomy, boundary dimension and anchor. It consumes zero model tokens and never replaces the required independent semantic rater; disagreement remains `needs_review`.

After evidence-backed manual review, import a private teacher-blind hidden seed and create leakage-safe splits:

```bash
python3 scripts/dataset_forge.py --root data/dataset-forge/pilot review --input manual-review.jsonl
python3 scripts/dataset_forge.py --root data/dataset-forge/pilot import-hidden --input hidden-seed.jsonl
python3 scripts/dataset_forge.py --root data/dataset-forge/pilot split
python3 scripts/dataset_forge.py --root data/dataset-forge/pilot report \
  --json-out reports/generated/dataset-forge.json \
  --markdown-out reports/generated/dataset-forge.md
```

## Recovery Guarantees

- Stable target and example IDs make retries idempotent.
- Each completed batch is checkpointed; terminal failures are append-only records.
- Concurrent workers return results to a deterministic main-thread writer.
- Fireworks budget is checked before each request and reconciled from actual usage.
- Exact hashes, token shingles and SimHash remove duplicates while preserving declared boundary pairs.
- Connected components over template family and mutation lineage prevent split leakage.

## Pilot Decision

The 120-row pilot passed schema validity, duplication, recovery and cost gates. It produced 120 accepted labels after independent ratings and evidence-backed adjudication, at `$0.0192993` billable Fireworks cost. The result is sufficient for an initial baseline and learning-curve point, but not presumed sufficient for the final model. Scaling is promoted only if held-out FunctionGemma metrics improve with additional data.

Public aggregate evidence is in [`reports/public/functiongemma-dataset-pilot.md`](../reports/public/functiongemma-dataset-pilot.md). Raw proposals, private labels and hidden test data remain ignored.
