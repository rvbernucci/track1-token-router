#!/bin/sh
set -eu

fg_pid=""
e2b_pid=""
runtime_dir="${PROOFROUTE_RUNTIME_DIR:-/tmp/proofroute}"

mkdir -p "$runtime_dir"
export HOME="${PROOFROUTE_HOME:-$runtime_dir}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$runtime_dir/cache}"
export ROUTER_LOG_PATH="${ROUTER_LOG_PATH:-$runtime_dir/run.jsonl}"
mkdir -p "$XDG_CACHE_HOME" "$(dirname "$ROUTER_LOG_PATH")"

cleanup() {
  [ -z "$fg_pid" ] || kill "$fg_pid" 2>/dev/null || true
  [ -z "$e2b_pid" ] || kill "$e2b_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait_for_url() {
  name="$1"
  url="$2"
  attempts="$3"
  while [ "$attempts" -gt 0 ]; do
    if curl --fail --silent --show-error "$url" >/dev/null 2>&1; then
      return 0
    fi
    attempts=$((attempts - 1))
    sleep 1
  done
  echo "$name failed to become ready: $url" >&2
  return 1
}

remote_only() {
  reason="$1"
  echo "local runtime unavailable; continuing with Fireworks: $reason" >&2
  cleanup
  fg_pid=""
  e2b_pid=""
  export ROUTER_MODE=fireworks
  exec router submit-track1
}

if [ "${PROOFROUTE_DISABLE_LOCAL:-0}" = "1" ]; then
  remote_only "disabled by runtime policy"
fi

/opt/llama/llama-server \
  --model /app/artifacts/functiongemma-scale789/functiongemma-scale789-q8_0.gguf \
  --alias functiongemma-q8 \
  --ctx-size 2048 \
  --threads 2 \
  --parallel 1 \
  --host 127.0.0.1 \
  --port 8091 \
  --jinja \
  >"$runtime_dir/functiongemma-server.log" 2>&1 &
fg_pid=$!

python /app/scripts/litert_cpu_server.py \
  --host 127.0.0.1 \
  --port 9379 \
  --cpu-threads 2 \
  --max-context-tokens 2048 \
  >"$runtime_dir/e2b-server.log" 2>&1 &
e2b_pid=$!

wait_for_url "FunctionGemma" "http://127.0.0.1:8091/health" 30 \
  || remote_only "FunctionGemma startup failure"
wait_for_url "Gemma E2B" "http://127.0.0.1:9379/v1/models" 30 \
  || remote_only "Gemma E2B startup failure"

exec router submit-track1
