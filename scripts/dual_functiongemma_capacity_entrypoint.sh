#!/bin/sh
set -eu

runtime_dir=/tmp/proofroute-dual
mkdir -p "$runtime_dir"
export HOME="$runtime_dir"
export XDG_CACHE_HOME="$runtime_dir/cache"
mkdir -p "$XDG_CACHE_HOME"

pids=""
cleanup() {
  for pid in $pids; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

start_functiongemma() {
  alias="$1"
  port="$2"
  /opt/llama/llama-server \
    --model /app/artifacts/functiongemma-scale789/functiongemma-scale789-q8_0.gguf \
    --alias "$alias" --ctx-size 1024 --threads 2 --parallel 1 \
    --host 127.0.0.1 --port "$port" --jinja \
    >"$runtime_dir/$alias.log" 2>&1 &
  pids="$pids $!"
}

start_functiongemma functiongemma-assessment 8091
start_functiongemma functiongemma-planner 8092

python /app/scripts/litert_cpu_server.py \
  --host 127.0.0.1 --port 9379 --cpu-threads 2 --max-context-tokens 1024 \
  >"$runtime_dir/e2b.log" 2>&1 &
pids="$pids $!"

for endpoint in http://127.0.0.1:8091/health http://127.0.0.1:8092/health http://127.0.0.1:9379/v1/models; do
  attempts=45
  until curl -fsS "$endpoint" >/dev/null; do
    attempts=$((attempts - 1))
    [ "$attempts" -gt 0 ] || { echo "startup failed: $endpoint" >&2; exit 1; }
    sleep 1
  done
done

touch "$runtime_dir/ready"
while :; do sleep 60; done
