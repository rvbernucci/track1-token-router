#!/usr/bin/env sh
set -eu

python3 -m unittest discover -s tests
python3 -m router ask "What is 2+2?"
python3 -m router eval \
  --jsonl evals/golden/tasks.jsonl \
  --expected evals/golden/expected.jsonl \
  --out reports/generated/golden-output.jsonl \
  --report reports/generated/golden-report.md
