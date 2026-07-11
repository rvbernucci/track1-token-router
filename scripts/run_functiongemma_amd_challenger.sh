#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/workspace/sprint56-amd}"
ARCHIVE="/workspace/sprint56-amd-parity.tar.gz"
PACKAGE_SHA="e7d9938435ebb3ec42ef88cc0128296dad06bfc5688b83d886214e8097ee31f8"
LLAMA_SHA="411d75cb580536248097afb1e6a512232c18f188fa05622fa60c175f413f570d"
LLAMA_URL="https://github.com/ggml-org/llama.cpp/releases/download/b9948/llama-b9948-bin-ubuntu-rocm-7.2-x64.tar.gz"

printf '%s  %s\n' "$PACKAGE_SHA" "$ARCHIVE" | sha256sum -c -
mkdir -p "$ROOT"
if [[ ! -f "$ROOT/.package-extracted" ]]; then
  tar -xzf "$ARCHIVE" -C "$ROOT"
  touch "$ROOT/.package-extracted"
fi
cd "$ROOT"

mkdir -p tools/llama-rocm-b9948
if [[ ! -x tools/llama-rocm-b9948/llama-server ]]; then
  llama_archive="/workspace/llama-rocm-b9948.tar.gz"
  if [[ ! -f "$llama_archive" ]]; then
    curl -k -fL --retry 5 -o "$llama_archive" "$LLAMA_URL"
  fi
  printf '%s  %s\n' "$LLAMA_SHA" "$llama_archive" | sha256sum -c -
  tar -xzf "$llama_archive" -C tools/llama-rocm-b9948 --strip-components=1
fi

mkdir -p evals/e2b-regression-v2-inference-amd/state
tools/llama-rocm-b9948/llama-server \
  --model artifacts/functiongemma-scale789/functiongemma-scale789-q8_0.gguf \
  --alias functiongemma-q8-amd \
  --ctx-size 2048 \
  --threads 8 \
  --parallel 1 \
  --n-gpu-layers 99 \
  --host 127.0.0.1 \
  --port 8091 \
  --jinja \
  > evals/e2b-regression-v2-inference-amd/state/server.log 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT

for _ in $(seq 1 120); do
  curl -fsS http://127.0.0.1:8091/health >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS http://127.0.0.1:8091/health >/dev/null

python3 scripts/run_e2b_regression_v2_inference.py \
  --resume \
  --only functiongemma \
  --output evals/e2b-regression-v2-inference-amd \
  --functiongemma-base-url http://127.0.0.1:8091/v1 \
  --functiongemma-model functiongemma-q8-amd

python3 scripts/run_e2b_regression_v2_inference.py \
  --check \
  --only functiongemma \
  --output evals/e2b-regression-v2-inference-amd \
  > evals/e2b-regression-v2-inference-amd/state/check.json
