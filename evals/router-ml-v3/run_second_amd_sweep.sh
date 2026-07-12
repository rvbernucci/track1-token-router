#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/workspace/track1-token-router-s77}"
PYTHON="${PYTHON:-/opt/venv/bin/python}"
cd "$ROOT"

mkdir -p reports/generated/router-ml-v3
python3 scripts/build_router_ml_v3_ledger.py

exec "$PYTHON" scripts/fit_router_ml_v3.py \
  --backend torch \
  --device cuda \
  --sweep \
  --intent-challenger \
  --sweep-configs 24 \
  --intent-configs 8 \
  --seeds 5 \
  --folds 5 \
  --epochs 500 \
  --checkpoint reports/generated/router-ml-v3/shared-onehot-sweep-checkpoint.json \
  --intent-checkpoint reports/generated/router-ml-v3/per-intent-sweep-checkpoint.json \
  --output evals/router-ml-v3/candidate-challenger.json \
  --report reports/generated/router-ml-v3/challenger-fit-report.json
