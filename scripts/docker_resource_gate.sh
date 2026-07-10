#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${1:-track1-token-router}"
REPORT="${2:-$ROOT/reports/generated/docker-resource-gate.json}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

command -v docker >/dev/null || { printf 'docker is required\n' >&2; exit 41; }
mkdir -p "$TMP/input" "$TMP/output" "$(dirname "$REPORT")"
cp "$ROOT/fixtures/official/lablab_track1_tasks.json" "$TMP/input/tasks.json"

platform="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$IMAGE")"
[ "$platform" = "linux/amd64" ] || { printf 'expected linux/amd64, got %s\n' "$platform" >&2; exit 42; }

uncompressed_size="$(docker image inspect --format '{{.Size}}' "$IMAGE")"
compressed_size="$(docker save "$IMAGE" | gzip -1 | wc -c | tr -d ' ')"
[ "$compressed_size" -le 10000000000 ] || { printf 'compressed image exceeds 10GB\n' >&2; exit 43; }

started="$(date +%s)"
timeout 600 docker run --rm \
  --memory=4g \
  --cpus=2 \
  --network=none \
  -e ROUTER_MODE=mock \
  -e ROUTER_RESOURCE_REPORT=/output/resource-usage.json \
  -v "$TMP/input:/input:ro" \
  -v "$TMP/output:/output" \
  "$IMAGE"
elapsed="$(( $(date +%s) - started ))"

python3 - "$TMP/output/results.json" "$TMP/output/resource-usage.json" "$REPORT" "$platform" "$compressed_size" "$uncompressed_size" "$elapsed" <<'PY'
import json
from pathlib import Path
import sys

results_path = Path(sys.argv[1])
resource_path = Path(sys.argv[2])
report_path = Path(sys.argv[3])
payload = json.loads(results_path.read_text(encoding="utf-8"))
resources = json.loads(resource_path.read_text(encoding="utf-8"))
if not isinstance(payload, list) or not payload:
    raise SystemExit("results.json must be a non-empty JSON array")
for row in payload:
    if (
        not isinstance(row, dict)
        or set(row) != {"task_id", "answer"}
        or not isinstance(row.get("task_id"), str)
        or not isinstance(row.get("answer"), str)
    ):
        raise SystemExit("results.json row violates the official output contract")
report = {
    "schema_version": "docker-resource-gate-v1",
    "ok": True,
    "image": sys.argv[4],
    "compressed_size_bytes": int(sys.argv[5]),
    "uncompressed_size_bytes": int(sys.argv[6]),
    "memory_limit_bytes": 4 * 1024**3,
    "cpus": 2,
    "network": "none",
    "maximum_runtime_seconds": 600,
    "observed_runtime_seconds": int(sys.argv[7]),
    "process_elapsed_ms": int(resources["elapsed_ms"]),
    "process_max_rss_mib": float(resources["max_rss_mib"]),
    "result_rows": len(payload),
}
report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(report, sort_keys=True))
PY
