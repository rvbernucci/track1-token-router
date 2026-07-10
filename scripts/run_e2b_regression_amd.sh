#!/usr/bin/env bash
set -u

WORKSPACE=/workspace
PROJECT="$WORKSPACE/track1-sprint46"
RUN="$WORKSPACE/e2b-regression-2000"
FG_PID_FILE="$RUN/functiongemma-run.pid"
FG_PREDICTIONS="$RUN/functiongemma-predictions.jsonl"
FG_REPORT="$RUN/functiongemma-report.json"
E2B_OUTPUT="$RUN/e2b-candidates-96.jsonl"
STATUS="$RUN/pipeline.status"

printf 'WAITING_FUNCTIONGEMMA\n' >"$STATUS"
while [ ! -s "$FG_PID_FILE" ]; do sleep 5; done
fg_pid="$(cat "$FG_PID_FILE")"
while kill -0 "$fg_pid" 2>/dev/null; do
  printf 'FUNCTIONGEMMA rows=%s\n' "$(wc -l <"$FG_PREDICTIONS" 2>/dev/null || printf 0)" >"$STATUS"
  sleep 20
done

fg_rows="$(wc -l <"$FG_PREDICTIONS" 2>/dev/null || printf 0)"
if [ "$fg_rows" -ne 2000 ] || [ ! -s "$FG_REPORT" ]; then
  printf 'FAILED_FUNCTIONGEMMA rows=%s\n' "$fg_rows" >"$STATUS"
  exit 21
fi

python3 "$PROJECT/scripts/filter_valid_assessments.py" \
  --tasks "$RUN/tasks.jsonl" \
  --assessments "$FG_PREDICTIONS" \
  --valid-tasks "$RUN/functiongemma-valid-tasks.jsonl" \
  --valid-assessments "$RUN/functiongemma-valid-predictions.jsonl" \
  --report "$RUN/functiongemma-filter-report.json" \
  >"$RUN/functiongemma-filter.log" 2>"$RUN/functiongemma-filter.err" || {
    printf 'FAILED_FUNCTIONGEMMA_FILTER\n' >"$STATUS"
    exit 25
  }
valid_rows="$(wc -l <"$RUN/functiongemma-valid-tasks.jsonl")"

printf 'STARTING_E2B rows=%s\n' "$(wc -l <"$E2B_OUTPUT" 2>/dev/null || printf 0)" >"$STATUS"
fuser -k 9379/tcp >"$RUN/e2b-fuser.log" 2>&1 || true
cd "$PROJECT" || exit 22
nohup taskset -c 0,1 /root/.local/share/uv/tools/litert-lm/bin/python \
  scripts/litert_cpu_server.py \
  --host 127.0.0.1 \
  --port 9379 \
  --cpu-threads 2 \
  --max-context-tokens 2048 \
  >"$RUN/e2b-server.log" 2>"$RUN/e2b-server.err" &
e2b_server_pid=$!
printf '%s\n' "$e2b_server_pid" >"$RUN/e2b-server.pid"

ready=0
for _attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:9379/v1/models >"$RUN/e2b-models.json"; then
    ready=1
    break
  fi
  sleep 2
done
if [ "$ready" -ne 1 ]; then
  printf 'FAILED_E2B_SERVER\n' >"$STATUS"
  kill "$e2b_server_pid" 2>/dev/null || true
  exit 23
fi

printf 'RUNNING_E2B rows=%s\n' "$(wc -l <"$E2B_OUTPUT" 2>/dev/null || printf 0)" >"$STATUS"
python3 scripts/e2b_outcome_experiment.py \
  --tasks "$RUN/functiongemma-valid-tasks.jsonl" \
  --assessments "$RUN/functiongemma-valid-predictions.jsonl" \
  --output "$E2B_OUTPUT" \
  --base-url http://127.0.0.1:9379/v1 \
  --model gemma4-e2b \
  --max-tokens 96 \
  --timeout-s 120 \
  --runtime-id standard-cpu-context2048-cap96 \
  >"$RUN/e2b-run.log" 2>"$RUN/e2b-run.err"
run_exit=$?
e2b_rows="$(wc -l <"$E2B_OUTPUT" 2>/dev/null || printf 0)"
kill "$e2b_server_pid" 2>/dev/null || true

if [ "$run_exit" -ne 0 ] || [ "$e2b_rows" -ne "$valid_rows" ]; then
  printf 'FAILED_E2B exit=%s rows=%s\n' "$run_exit" "$e2b_rows" >"$STATUS"
  exit 24
fi
printf 'COMPLETE rows=%s\n' "$e2b_rows" >"$STATUS"
