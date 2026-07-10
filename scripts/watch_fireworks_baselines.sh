#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -z "${PYTHON_BIN:-}" ]; then
  if [ -x /opt/homebrew/bin/python3 ]; then
    PYTHON_BIN=/opt/homebrew/bin/python3
  else
    PYTHON_BIN="$(command -v python3)"
  fi
fi
RUN="$ROOT/reports/generated/e2b-2000-baselines"
MINIMAX="$RUN/minimax-m3-runtime-v4-candidates.jsonl"
KIMI="$RUN/kimi-k2p7-code-runtime-v4-candidates.jsonl"
JUDGMENTS="$RUN/fireworks-runtime-v4-judgments.jsonl"
STATUS="$RUN/watcher.status"
EXPECTED=571
LOCK_DIR="$RUN/watcher.lockdir"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  printf 'DUPLICATE_WATCHER_REFUSED\n' >"$STATUS"
  exit 47
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || {
  printf 'FAILED_PYTHON_VERSION %s\n' "$PYTHON_BIN" >"$STATUS"
  exit 48
}

rows() { wc -l <"$1" 2>/dev/null || printf 0; }

while [ "$(rows "$MINIMAX")" -lt "$EXPECTED" ] || [ "$(rows "$KIMI")" -lt "$EXPECTED" ]; do
  printf 'WAITING_CANDIDATES minimax=%s kimi=%s\n' "$(rows "$MINIMAX")" "$(rows "$KIMI")" >"$STATUS"
  sleep 30
done

set -a
[ -f "$ROOT/.env.fireworks" ] && . "$ROOT/.env.fireworks"
[ -f "$ROOT/.env.fireworks.local" ] && . "$ROOT/.env.fireworks.local"
set +a
: "${FIREWORKS_API_KEY:?FIREWORKS_API_KEY is required for cross-model judging}"

run_judge() {
  provider="$1"
  model="$2"
  candidates="$3"
  budget="$4"
  for batch_size in 32 16 8 4 2 1; do
    if DATASET_AGY_EXPECTED_EMAIL="${DATASET_AGY_EXPECTED_EMAIL:-rvbernucci@gmail.com}" \
      "$PYTHON_BIN" "$ROOT/scripts/judge_engine_outcomes.py" \
        --provider "$provider" \
        --candidates "$candidates" \
        --output "$JUDGMENTS" \
        --model "$model" \
        --batch-size "$batch_size" \
        --max-tokens 4096 \
        --budget-usd "$budget"; then
      return 0
    fi
  done
  return 1
}

printf 'JUDGING_MINIMAX_WITH_KIMI\n' >"$STATUS"
run_judge fireworks accounts/fireworks/models/kimi-k2p7-code "$MINIMAX" "${KIMI_JUDGE_BUDGET_USD:-1.50}" || { printf 'FAILED_MINIMAX_KIMI_JUDGE\n' >"$STATUS"; exit 41; }
printf 'JUDGING_MINIMAX_GEMINI\n' >"$STATUS"
run_judge agy 'Gemini 3.5 Flash (Medium)' "$MINIMAX" 0 || { printf 'FAILED_MINIMAX_GEMINI\n' >"$STATUS"; exit 42; }
printf 'JUDGING_KIMI_WITH_MINIMAX\n' >"$STATUS"
run_judge fireworks accounts/fireworks/models/minimax-m3 "$KIMI" "${MINIMAX_JUDGE_BUDGET_USD:-0.75}" || { printf 'FAILED_KIMI_MINIMAX_JUDGE\n' >"$STATUS"; exit 43; }
printf 'JUDGING_KIMI_GEMINI\n' >"$STATUS"
run_judge agy 'Gemini 3.5 Flash (Medium)' "$KIMI" 0 || { printf 'FAILED_KIMI_GEMINI\n' >"$STATUS"; exit 44; }

"$PYTHON_BIN" - "$MINIMAX" "$KIMI" "$JUDGMENTS" "$STATUS" <<'PY'
import collections,json,sys

candidate_paths = {
    sys.argv[1]: ("accounts/fireworks/models/kimi-k2p7-code", "Gemini 3.5 Flash (Medium)"),
    sys.argv[2]: ("accounts/fireworks/models/minimax-m3", "Gemini 3.5 Flash (Medium)"),
}
expected = {}
for path, judges in candidate_paths.items():
    for row in map(json.loads, open(path, encoding="utf-8")):
        if not row.get("failure") and not row.get("refusal"):
            expected[row["id"]] = set(judges)
seen = collections.defaultdict(set)
duplicates = []
for row in map(json.loads, open(sys.argv[3], encoding="utf-8")):
    candidate_id = row["candidate_id"]
    judge = row["judge_model"]
    if candidate_id not in expected or judge not in expected[candidate_id]:
        continue
    if judge in seen[candidate_id]:
        duplicates.append((candidate_id, judge))
    seen[candidate_id].add(judge)
missing = {
    candidate_id: sorted(judges - seen[candidate_id])
    for candidate_id, judges in expected.items()
    if judges - seen[candidate_id]
}
if duplicates or missing:
    payload = {"duplicates": len(duplicates), "missing": len(missing)}
    open(sys.argv[4], "w").write("FAILED_JUDGMENT_COVERAGE " + json.dumps(payload, sort_keys=True) + "\n")
    raise SystemExit(45)
counts = collections.Counter(
    row["judge_model"]
    for row in map(json.loads, open(sys.argv[3], encoding="utf-8"))
    if row["candidate_id"] in expected and row["judge_model"] in expected[row["candidate_id"]]
)
open(sys.argv[4], "w").write("COMPLETE " + json.dumps(counts, sort_keys=True) + "\n")
PY

"$PYTHON_BIN" "$ROOT/scripts/compare_fireworks_baselines.py" \
  --tasks "$RUN/validation-test-tasks.jsonl" \
  --candidate "$MINIMAX" \
  --candidate "$KIMI" \
  --judgments "$JUDGMENTS" \
  --judge-policy "$ROOT/configs/fireworks-baseline-judge-policy.json" \
  --output "$RUN/fireworks-baseline-comparison.json" \
  --markdown "$RUN/fireworks-baseline-comparison.md" \
  >"$RUN/compare.log" 2>"$RUN/compare.err" || {
    printf 'FAILED_BASELINE_COMPARISON\n' >"$STATUS"
    exit 46
  }
printf 'COMPLETE_COMPARISON\n' >"$STATUS"
