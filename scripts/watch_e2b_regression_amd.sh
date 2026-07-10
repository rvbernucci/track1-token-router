#!/usr/bin/env bash
set -u

: "${AMD_NOTEBOOK_BASE_URL:?AMD_NOTEBOOK_BASE_URL is required}"
: "${AMD_NOTEBOOK_TOKEN:?AMD_NOTEBOOK_TOKEN is required}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -z "${PYTHON_BIN:-}" ]; then
  if [ -x /opt/homebrew/bin/python3 ]; then
    PYTHON_BIN=/opt/homebrew/bin/python3
  else
    PYTHON_BIN="$(command -v python3)"
  fi
fi
REMOTE_DIR=e2b-regression-2000
LOCAL_DIR="$ROOT/reports/generated/amd-pod-e2b-regression-2000"
STATUS="$LOCAL_DIR/watcher.status"
JUDGMENTS="$LOCAL_DIR/e2b-judgments.jsonl"
mkdir -p "$LOCAL_DIR"
LOCK_DIR="$LOCAL_DIR/watcher.lockdir"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  printf 'DUPLICATE_WATCHER_REFUSED\n' >"$STATUS"
  exit 40
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || {
  printf 'FAILED_PYTHON_VERSION %s\n' "$PYTHON_BIN" >"$STATUS"
  exit 43
}

remote_file() {
  curl --max-time 20 -fsSL \
    "$AMD_NOTEBOOK_BASE_URL/files/$REMOTE_DIR/$1?token=$AMD_NOTEBOOK_TOKEN"
}

download_file() {
  filename="$1"
  destination="$2"
  temporary="${destination}.partial"
  rm -f "$temporary"
  if ! curl \
    --connect-timeout 20 \
    --max-time 300 \
    --retry 5 \
    --retry-all-errors \
    --retry-delay 2 \
    -fsSL \
    "$AMD_NOTEBOOK_BASE_URL/files/$REMOTE_DIR/$filename?token=$AMD_NOTEBOOK_TOKEN" \
    >"$temporary"; then
    rm -f "$temporary"
    return 1
  fi
  mv "$temporary" "$destination"
}

while true; do
  remote_status="$(remote_file pipeline.status 2>/dev/null || true)"
  printf '%s %s\n' "$(date -u +%FT%TZ)" "${remote_status:-UNREACHABLE}" >"$STATUS"
  case "$remote_status" in
    COMPLETE*) break ;;
    FAILED*) exit 31 ;;
  esac
  sleep 60
done

for filename in tasks.jsonl manifest.json functiongemma-predictions.jsonl functiongemma-report.json functiongemma-valid-tasks.jsonl functiongemma-valid-predictions.jsonl functiongemma-filter-report.json e2b-candidates-96.jsonl e2b-run.log; do
  download_file "$filename" "$LOCAL_DIR/$filename" || {
    printf 'FAILED_DOWNLOAD %s\n' "$filename" >"$STATUS"
    exit 32
  }
done

for filename in tasks.jsonl functiongemma-predictions.jsonl; do
  rows="$(wc -l <"$LOCAL_DIR/$filename")"
  if [ "$rows" -ne 2000 ]; then
    printf 'FAILED_DOWNLOAD %s rows=%s\n' "$filename" "$rows" >"$STATUS"
    exit 32
  fi
done
valid_rows="$(wc -l <"$LOCAL_DIR/functiongemma-valid-tasks.jsonl")"
candidate_rows="$(wc -l <"$LOCAL_DIR/e2b-candidates-96.jsonl")"
if [ "$valid_rows" -lt 1 ] || [ "$candidate_rows" -ne "$valid_rows" ]; then
  printf 'FAILED_VALID_CANDIDATE_COUNTS valid=%s candidates=%s\n' "$valid_rows" "$candidate_rows" >"$STATUS"
  exit 38
fi
shasum -a 256 "$LOCAL_DIR"/* >"$LOCAL_DIR/download-sha256.txt"

set -a
[ -f "$ROOT/.env.fireworks" ] && . "$ROOT/.env.fireworks"
[ -f "$ROOT/.env.fireworks.local" ] && . "$ROOT/.env.fireworks.local"
set +a
: "${FIREWORKS_API_KEY:?FIREWORKS_API_KEY is required for judging}"

run_resumable_judge() {
  provider="$1"
  model="$2"
  for batch_size in 32 16 8 4 2 1; do
    if DATASET_AGY_EXPECTED_EMAIL="${DATASET_AGY_EXPECTED_EMAIL:-rvbernucci@gmail.com}" \
      "$PYTHON_BIN" "$ROOT/scripts/judge_engine_outcomes.py" \
        --provider "$provider" \
        --candidates "$LOCAL_DIR/e2b-candidates-96.jsonl" \
        --output "$JUDGMENTS" \
        --model "$model" \
        --batch-size "$batch_size" \
        --max-tokens 4096 \
        --budget-usd "${E2B_JUDGE_BUDGET_USD:-2.50}"; then
      return 0
    fi
  done
  return 1
}

printf 'JUDGING_KIMI\n' >"$STATUS"
run_resumable_judge fireworks accounts/fireworks/models/kimi-k2p7-code || {
  printf 'FAILED_KIMI_JUDGE\n' >"$STATUS"
  exit 33
}

printf 'JUDGING_GEMINI\n' >"$STATUS"
run_resumable_judge agy 'Gemini 3.5 Flash (Medium)' || {
  printf 'FAILED_GEMINI_JUDGE\n' >"$STATUS"
  exit 34
}

kimi_rows="$(grep -c 'accounts/fireworks/models/kimi-k2p7-code' "$JUDGMENTS" || true)"
gemini_rows="$(grep -c 'Gemini 3.5 Flash (Medium)' "$JUDGMENTS" || true)"
if [ "$kimi_rows" -ne "$valid_rows" ] || [ "$gemini_rows" -ne "$valid_rows" ]; then
  printf 'FAILED_JUDGMENT_COUNTS kimi=%s gemini=%s\n' "$kimi_rows" "$gemini_rows" >"$STATUS"
  exit 35
fi

printf 'AUDITING_RESCUE_GATE\n' >"$STATUS"
"$PYTHON_BIN" "$ROOT/scripts/audit_e2b_rescue_gate.py" \
  --tasks "$LOCAL_DIR/functiongemma-valid-tasks.jsonl" \
  --candidates "$LOCAL_DIR/e2b-candidates-96.jsonl" \
  --judgments "$JUDGMENTS" \
  --judge-policy "$ROOT/configs/e2b-regression-judge-policy.json" \
  --output "$LOCAL_DIR/e2b-rescue-gate-audit.json" \
  --report "$LOCAL_DIR/e2b-rescue-gate-audit.md" \
  >"$LOCAL_DIR/rescue-gate.log" 2>"$LOCAL_DIR/rescue-gate.err" || {
    printf 'FAILED_RESCUE_GATE_AUDIT\n' >"$STATUS"
    exit 42
  }

printf 'BUILDING_MATRIX kimi=%s gemini=%s\n' "$kimi_rows" "$gemini_rows" >"$STATUS"
"$PYTHON_BIN" "$ROOT/scripts/build_engine_outcome_matrix.py" \
  --tasks "$LOCAL_DIR/functiongemma-valid-tasks.jsonl" \
  --assessments "$LOCAL_DIR/functiongemma-valid-predictions.jsonl" \
  --calibration "$ROOT/configs/functiongemma-scale789-q8-calibration.json" \
  --judge-policy "$ROOT/configs/e2b-regression-judge-policy.json" \
  --competition-snapshot "$ROOT/configs/track1-competition-snapshot-20260710.json" \
  --candidate "$LOCAL_DIR/e2b-candidates-96.jsonl" \
  --judgments "$JUDGMENTS" \
  --output "$LOCAL_DIR/e2b-outcome-matrix.jsonl" \
  --report "$LOCAL_DIR/e2b-outcome-matrix-report.json" \
  >"$LOCAL_DIR/build-matrix.log" 2>"$LOCAL_DIR/build-matrix.err" || {
    printf 'FAILED_MATRIX_BUILD\n' >"$STATUS"
    exit 36
  }

printf 'FITTING_REGRESSION\n' >"$STATUS"
"$PYTHON_BIN" "$ROOT/scripts/fit_engine_outcome_models.py" \
  --matrix "$LOCAL_DIR/e2b-outcome-matrix.jsonl" \
  --output "$LOCAL_DIR/e2b-outcome-models.json" \
  --report "$LOCAL_DIR/e2b-outcome-regression-report.md" \
  >"$LOCAL_DIR/fit-regression.log" 2>"$LOCAL_DIR/fit-regression.err" || {
    printf 'FAILED_REGRESSION_FIT\n' >"$STATUS"
    exit 37
  }

printf 'ANALYZING_LEARNING_CURVE\n' >"$STATUS"
"$PYTHON_BIN" "$ROOT/scripts/analyze_regression_learning_curve.py" \
  --matrix "$LOCAL_DIR/e2b-outcome-matrix.jsonl" \
  --engine gemma4-e2b \
  --sizes 100,250,500,1000 \
  --repeats 5 \
  --output "$LOCAL_DIR/e2b-regression-learning-curve.json" \
  --report "$LOCAL_DIR/e2b-regression-learning-curve.md" \
  >"$LOCAL_DIR/learning-curve.log" 2>"$LOCAL_DIR/learning-curve.err" || {
    printf 'FAILED_LEARNING_CURVE\n' >"$STATUS"
    exit 41
  }

printf 'AUDITING_E2B_PROMOTION\n' >"$STATUS"
"$PYTHON_BIN" "$ROOT/scripts/promote_e2b_policy.py" \
  --matrix "$LOCAL_DIR/e2b-outcome-matrix.jsonl" \
  --models "$LOCAL_DIR/e2b-outcome-models.json" \
  --base-policy "$ROOT/configs/e2b-route-policy-v1.json" \
  --output-policy "$LOCAL_DIR/e2b-route-policy-candidate.json" \
  --report "$LOCAL_DIR/e2b-promotion-report.json" \
  --accuracy-gate "${THREE_ROUTE_ACCURACY_GATE:-0.60}" \
  --minimum-selected "${E2B_MINIMUM_LOCKED_TEST_SELECTED:-30}" \
  >"$LOCAL_DIR/promote-e2b.log" 2>"$LOCAL_DIR/promote-e2b.err" || {
    printf 'FAILED_E2B_PROMOTION_AUDIT\n' >"$STATUS"
    exit 39
  }

shasum -a 256 \
  "$LOCAL_DIR/e2b-outcome-matrix.jsonl" \
  "$LOCAL_DIR/e2b-outcome-models.json" \
  "$LOCAL_DIR/e2b-regression-learning-curve.json" \
  "$LOCAL_DIR/e2b-rescue-gate-audit.json" \
  "$LOCAL_DIR/e2b-route-policy-candidate.json" \
  >"$LOCAL_DIR/analysis-sha256.txt"
promotion="$("$PYTHON_BIN" -c 'import json,sys; print(str(json.load(open(sys.argv[1]))["decision"]["promoted"]).lower())' "$LOCAL_DIR/e2b-promotion-report.json")"
printf 'COMPLETE kimi=%s gemini=%s matrix=%s excluded=%s e2b_promoted=%s\n' "$kimi_rows" "$gemini_rows" "$valid_rows" "$((2000-valid_rows))" "$promotion" >"$STATUS"
