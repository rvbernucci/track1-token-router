# Recording Shotlist

Target duration: 4 to 5 minutes.

## Scene 1 - Hook

- Timebox: 0:00-0:25.
- Visual: static demo hero or title slide.
- Message: Track 1 is won by knowing when not to spend remote tokens.
- Command on screen: none.

## Scene 2 - Problem

- Timebox: 0:25-0:55.
- Visual: architecture slide.
- Message: naive routing either wastes Fireworks tokens or returns cheap wrong answers.
- Command on screen: none.

## Scene 3 - Architecture

- Timebox: 0:55-1:45.
- Visual: router flow in `demo-site/index.html`.
- Message: FunctionGemma assesses; regression and minimax choose deterministic, Gemma E2B or Fireworks.
- Command on screen:

```bash
python3 scripts/export_public_report.py --check
```

## Scene 4 - Zero-Remote Solver Demo

- Timebox: 1:45-2:30.
- Visual: terminal.
- Message: mechanical tasks should not reach any model.
- Command on screen:

```bash
ROUTER_MODE=competition COMPETITION_DRY_RUN=1 \
python3 -m router ask "What is 6 * 7? Return only the number." --json
```

## Scene 5 - Battle Drill

- Timebox: 2:30-3:25.
- Visual: terminal plus report excerpt.
- Message: readiness is measured, not narrated.
- Command on screen:

```bash
python3 scripts/battle_drill.py
```

## Scene 6 - Operational Envelope

- Timebox: 3:25-4:10.
- Visual: latency/token reports.
- Message: the project tracks p95 latency and conservative token exposure before credits arrive.
- Commands on screen:

```bash
python3 scripts/latency_drill.py --check
python3 scripts/token_envelope.py --check
```

## Scene 7 - Close

- Timebox: 4:10-4:45.
- Visual: final slide or demo footer.
- Message: local intelligence by default, deterministic code when possible, remote power only when it materially improves correctness.
- Command on screen:

```bash
scripts/offline_release_check.sh
```
