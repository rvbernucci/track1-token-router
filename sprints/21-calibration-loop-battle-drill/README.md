# Sprint 21 - Calibration Loop & Battle Drill

## Type

Does not depend on credit.

## Objective

Create a calibration loop that runs datasets, compares policies, adjusts thresholds, and produces a battle report before the actual kickoff/scoring.

## Why it matters

Once orchestration exists, the advantage comes from iterating fast. We need a competition ritual: run, measure, adjust, and repeat.

## Deliverables

- `scripts/battle_drill.py` script.
- `reports/generated/battle-report.md` report.
- `reports/generated/battle-report.json` JSON.
- Configuration comparison.
- Ranking by offline score.
- Readiness checklist.
- Tests for the calibration pipeline.

## Checklist

- [x] Run full dataset offline.
- [x] Run policy comparison.
- [x] Run offline scoreboard.
- [x] Run prompt ablation.
- [x] Run trace analytics.
- [x] Run guardrail probes.
- [x] Compare at least 3 configurations.
- [x] Elect a candidate configuration.
- [x] Record the accuracy vs. remote token tradeoff.
- [x] Record remaining risks.
- [x] Generate Markdown battle report.
- [x] Generate JSON battle report.
- [x] Integrate with the release check or a dedicated command.

## Acceptance criteria

- A single command generates the competitive diagnosis.
- The report shows the best candidate configuration.
- The report shows why the alternatives lost.
- The process works without AMD and without Fireworks.

## Expected output

A calibration ritual to turn architecture into operational advantage.

## Local evidence

```bash
python3 scripts/battle_drill.py
python3 -m unittest tests.test_battle_drill
scripts/offline_release_check.sh
```

## Decision

The battle drill chooses the candidate configuration via the offline scoreboard and places policy comparison, policy ablation, prompt ablation, trace analytics, and guardrail probes side by side. It does not replace official scoring, but creates a repeatable ritual to arrive at kickoff with a strong hypothesis.
