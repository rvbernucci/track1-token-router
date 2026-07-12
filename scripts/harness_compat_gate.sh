#!/usr/bin/env bash
set -euo pipefail

IMAGE="${1:?usage: harness_compat_gate.sh IMAGE}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/input" "$TMP/output-local" "$TMP/output-fallback" "$TMP/output-missing"
chmod 755 "$TMP/input"
chmod 777 "$TMP/output-local" "$TMP/output-fallback" "$TMP/output-missing"

cat >"$TMP/input/tasks.json" <<'JSON'
[
  {"task_id":"local-1","prompt":"The product is excellent and I love it. Classify the sentiment as positive, negative, or neutral. Return only the label."},
  {"task_id":"local-2","prompt":"The service was awful and completely disappointing. Classify the sentiment as positive, negative, or neutral. Return only the label."}
]
JSON

common=(
  --rm --platform linux/amd64 --memory=4g --cpus=2 --network=none
  --read-only --user 65534:65534
  --tmpfs /tmp:rw,exec,nosuid,size=1g,mode=1777
)

# The official harness variables are required. Missing variables must fail clearly,
# not through a segfault, illegal instruction, or opaque startup crash.
set +e
docker run "${common[@]}" \
  -e PROOFROUTE_DISABLE_LOCAL=1 \
  -v "$TMP/input:/input:ro" \
  -v "$TMP/output-missing:/output" \
  "$IMAGE" >"$TMP/missing.stdout" 2>"$TMP/missing.stderr"
missing_rc=$?
set -e
test "$missing_rc" -ne 0
grep -q "Official Fireworks runtime requires harness variables" "$TMP/missing.stderr"

# Real local inference must survive a non-root user and read-only root filesystem.
docker run "${common[@]}" \
  -e FIREWORKS_API_KEY=self-check-local-only \
  -e FIREWORKS_BASE_URL=http://127.0.0.1:9/v1 \
  -e ALLOWED_MODELS=accounts/fireworks/models/kimi-k2p7-code \
  -v "$TMP/input:/input:ro" \
  -v "$TMP/output-local:/output" \
  "$IMAGE"

python3 - "$TMP/output-local/results.json" <<'PY'
import json
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))
assert len(rows) == 2
assert {row["answer"].strip().lower() for row in rows} == {"positive", "negative"}
PY

# If local runtimes are unavailable, deterministic work must still complete through
# the remote-safe runner without contacting the unreachable self-check endpoint.
cat >"$TMP/input/tasks.json" <<'JSON'
[{"task_id":"fallback-1","prompt":"What is 6 * 7? Return only the number."}]
JSON
docker run "${common[@]}" \
  -e PROOFROUTE_DISABLE_LOCAL=1 \
  -e FIREWORKS_API_KEY=self-check-deterministic-only \
  -e FIREWORKS_BASE_URL=http://127.0.0.1:9/v1 \
  -e ALLOWED_MODELS=accounts/fireworks/models/kimi-k2p7-code \
  -v "$TMP/input:/input:ro" \
  -v "$TMP/output-fallback:/output" \
  "$IMAGE"

python3 - "$TMP/output-fallback/results.json" <<'PY'
import json
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))
assert rows == [{"task_id": "fallback-1", "answer": "42"}]
PY

printf '{"image":"%s","missing_env":"clear_failure","read_only_non_root_local":"pass","local_failure_fallback":"pass"}\n' "$IMAGE"
