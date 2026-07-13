#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from time import perf_counter
from urllib.request import Request, urlopen


def main() -> int:
    prompt = "Return exactly OK and nothing else."
    payload = {
        "model": "gemma4-e2b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 96,
    }
    started = perf_counter()
    request = Request(
        os.environ.get("E2B_TEST_URL", "http://127.0.0.1:8080") + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=120) as response:
        body = json.load(response)
    answer = body["choices"][0]["message"]["content"].strip()
    result = {
        "answer": answer,
        "latency_ms": round((perf_counter() - started) * 1000, 2),
        "usage": body.get("usage", {}),
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if answer == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
