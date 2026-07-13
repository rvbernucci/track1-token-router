#!/usr/bin/env bash
set -euo pipefail

body='{"model":"gemma4-e2b","messages":[{"role":"user","content":"Return exactly OK and nothing else."}],"temperature":0,"max_tokens":96}'
exec 3<>/dev/tcp/127.0.0.1/8080
printf 'POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: %d\r\n\r\n%s' "${#body}" "$body" >&3
response=$(cat <&3)
printf '%s\n' "$response"
grep -q '"content":"OK"' <<<"$response"
