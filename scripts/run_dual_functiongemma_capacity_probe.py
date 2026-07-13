#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from urllib.request import Request, urlopen


ENDPOINTS = (
    ("assessment", "http://127.0.0.1:8091/v1/chat/completions", "functiongemma-assessment", 48),
    ("planner", "http://127.0.0.1:8092/v1/chat/completions", "functiongemma-planner", 48),
    ("e2b", "http://127.0.0.1:9379/v1/chat/completions", "gemma4-e2b", 24),
)


def main() -> int:
    output = Path("/tmp/proofroute-dual/probe.json")
    rows = []
    prompts = (
        "Classify the task: What is 2 + 2?",
        "A warehouse starts with 500 units, sells 10%, adds 30, then sells 20.",
        "Ana is taller than Ben. Who is shortest?",
        "Classify sentiment: The service was excellent.",
        "Return exactly OK and nothing else.",
    )
    for iteration in range(25):
        prompt = prompts[iteration % len(prompts)]
        for name, url, model, max_tokens in ENDPOINTS:
            started = perf_counter()
            body = _complete(url, model, prompt, max_tokens)
            rows.append({
                "iteration": iteration, "engine": name,
                "latency_ms": round((perf_counter() - started) * 1000, 2),
                "nonempty": bool(body["choices"][0]["message"].get("content", "").strip()),
                "usage": body.get("usage", {}),
            })
    summary = {
        "calls": len(rows), "iterations": 25,
        "failures": sum(not row["nonempty"] for row in rows),
        "mean_latency_ms": round(sum(row["latency_ms"] for row in rows) / len(rows), 2),
        "by_engine": {
            name: {
                "calls": sum(row["engine"] == name for row in rows),
                "failures": sum(row["engine"] == name and not row["nonempty"] for row in rows),
                "mean_latency_ms": round(
                    sum(row["latency_ms"] for row in rows if row["engine"] == name)
                    / sum(row["engine"] == name for row in rows), 2,
                ),
            }
            for name, *_ in ENDPOINTS
        },
    }
    output.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["failures"] == 0 else 2


def _complete(url: str, model: str, prompt: str, max_tokens: int) -> dict:
    payload = json.dumps({
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "temperature": 0, "max_tokens": max_tokens,
    }).encode()
    request = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=60) as response:
        return json.load(response)


if __name__ == "__main__":
    raise SystemExit(main())
