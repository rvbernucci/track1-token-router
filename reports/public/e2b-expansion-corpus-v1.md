# E2B Expansion Corpus V1

Sprint 70 adds `2,400` independent E2B evaluation tasks without opening the promotion holdout during model or threshold selection.

## Population

- Eight Track 1 categories with `300` tasks each.
- Three construction bands with `800` tasks each: easy, moderate and hard.
- `1,440` fit tasks, `480` calibration tasks and `480` sealed promotion tasks.
- `1,920` English, `240` Portuguese and `240` Spanish tasks.
- `1,200` Antigravity lineages and `1,200` Fireworks lineages.
- Fireworks generation cost: `$3.1369353`.

## Data Gates

- `4,480` historical prompts scanned.
- Zero normalized overlap with historical prompts.
- Zero internal normalized duplicates after targeted regeneration.
- Zero semantic near-duplicate pairs at the frozen audit threshold.
- Zero mutation-lineage leakage across protected splits.
- Zero prompts outside the local `2,048`-token context safety margin.
- Sealed tasks and references live in separate private paths and are excluded from Git.

## Provider Provenance

- Antigravity / Gemini 3.5 Flash Medium: `1,200` final tasks.
- Fireworks / MiniMax M3: `974` final tasks.
- Fireworks / Kimi K2.7 Code: `226` final tasks, including structured-generation recovery.

The declared difficulty band, generator identity, reference answer and judge outcome are audit metadata only. None is available to the production E2B routing regression.

## Reproduction

```bash
python3 scripts/generate_e2b_expansion.py
python3 scripts/audit_e2b_expansion_dedup.py
python3 scripts/generate_e2b_expansion.py --materialize --check
```

Generation requires authenticated provider accounts and an explicit Fireworks budget. The committed plan can be checked without credentials or provider calls.
