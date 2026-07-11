#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$HOME/track1-token-router}"
cd "$ROOT"

STATE="evals/e2b-regression-v2-inference/state"
OUTPUT="evals/e2b-regression-v2-inference"

wait_pid_file() {
  local file="$1"
  local pid
  pid="$(cat "$file")"
  while kill -0 "$pid" 2>/dev/null; do
    sleep 10
  done
}

wait_pid_file "$STATE/e2b-full.pid"
e2b_rows="$(wc -l < "$OUTPUT/e2b.jsonl")"
if [[ "$e2b_rows" -ne 2000 ]]; then
  printf 'E2B_INCOMPLETE rows=%s\n' "$e2b_rows"
  exit 1
fi

python3 scripts/run_e2b_regression_v2_inference.py \
  --check --only e2b > "$STATE/e2b-check.json"

python3 scripts/run_e2b_regression_v2_inference.py \
  --resume --only functiongemma \
  --functiongemma-base-url http://127.0.0.1:8091/v1 \
  > "$STATE/functiongemma-full.log" 2>&1 &
fg_pid=$!
printf '%s\n' "$fg_pid" > "$STATE/functiongemma-full.pid"
wait "$fg_pid"

python3 scripts/run_e2b_regression_v2_inference.py \
  --check > "$STATE/combined-check.json"

printf 'SPRINT56_INFERENCE_COMPLETE e2b=%s functiongemma=%s\n' \
  "$(wc -l < "$OUTPUT/e2b.jsonl")" \
  "$(wc -l < "$OUTPUT/functiongemma.jsonl")"
