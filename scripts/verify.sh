#!/usr/bin/env sh
set -eu

python3 -m unittest discover -s tests
python3 -m router ask "What is 2+2?"
python3 -m router eval \
  --jsonl evals/golden/tasks.jsonl \
  --expected evals/golden/expected.jsonl \
  --out reports/generated/golden-output.jsonl \
  --report reports/generated/golden-report.md
python3 scripts/generate_offline_eval.py --check
python3 -m router eval \
  --jsonl evals/offline/tasks.jsonl \
  --expected evals/offline/expected.jsonl \
  --out reports/generated/offline-output.jsonl \
  --report reports/generated/offline-report.md
