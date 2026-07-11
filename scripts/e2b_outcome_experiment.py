#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from router.core.e2b_runner import E2B_PROMPT_VERSION, build_e2b_messages


SCHEMA_VERSION = "e2b-answer-candidate-v2"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Run resumable Gemma E2B answer-candidate experiments.")
    root.add_argument("--tasks", type=Path, required=True)
    root.add_argument("--assessments", type=Path, required=True)
    root.add_argument("--output", type=Path, required=True)
    root.add_argument("--base-url", default="http://127.0.0.1:9379/v1")
    root.add_argument("--model", default="gemma4-e2b")
    root.add_argument("--max-tokens", type=int, default=96)
    root.add_argument("--timeout-s", type=float, default=120.0)
    root.add_argument("--runtime-id", default="litert-default")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    summary = run_experiment(
        tasks_path=args.tasks,
        assessments_path=args.assessments,
        output=args.output,
        base_url=args.base_url,
        model=args.model,
        max_tokens=args.max_tokens,
        timeout_s=args.timeout_s,
        runtime_id=args.runtime_id,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


def run_experiment(
    *,
    tasks_path: Path,
    assessments_path: Path,
    output: Path,
    base_url: str,
    model: str,
    max_tokens: int,
    timeout_s: float,
    runtime_id: str = "legacy",
) -> dict[str, Any]:
    if max_tokens < 1 or timeout_s <= 0:
        raise ValueError("max_tokens and timeout_s must be positive.")
    tasks = [_task(row) for row in _jsonl(tasks_path)]
    assessments = _assessment_index(_jsonl(assessments_path))
    missing = sorted(task_id for task_id, _ in tasks if task_id not in assessments)
    if missing:
        raise ValueError(f"Missing FunctionGemma assessments for {len(missing)} task(s).")
    existing = {
        str(row.get("task_id") or row["id"])
        for row in _jsonl(output)
    } if output.exists() else set()
    output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    failures = 0
    with output.open("a", encoding="utf-8") as handle:
        for task_id, task_text in tasks:
            if task_id in existing:
                continue
            row = _complete(
                task_id=task_id,
                task_text=task_text,
                assessment=assessments[task_id],
                base_url=base_url,
                model=model,
                max_tokens=max_tokens,
                timeout_s=timeout_s,
                runtime_id=runtime_id,
            )
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            written += 1
            failures += int(row["failure"])
    return {
        "schema_version": SCHEMA_VERSION,
        "tasks": len(tasks),
        "already_complete": len(existing & {task_id for task_id, _ in tasks}),
        "written": written,
        "failures": failures,
        "output": str(output),
    }


def _complete(
    *,
    task_id: str,
    task_text: str,
    assessment: Mapping[str, Any],
    base_url: str,
    model: str,
    max_tokens: int,
    timeout_s: float,
    runtime_id: str = "legacy",
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": build_e2b_messages(task_text),
        "temperature": 0,
        # LiteRT-LM 0.14 only enforces the current OpenAI field. Keep the
        # legacy alias for compatibility with older OpenAI-style adapters.
        "max_completion_tokens": max_tokens,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    answer = ""
    error = ""
    usage: Mapping[str, Any] = {}
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            response_payload = json.loads(response.read().decode())
        choices = response_payload.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError("E2B response must contain exactly one choice.")
        message = choices[0].get("message") if isinstance(choices[0], Mapping) else None
        content = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(content, str) or not content.strip():
            raise ValueError("E2B response content is empty.")
        answer = content.strip()
        raw_usage = response_payload.get("usage")
        usage = raw_usage if isinstance(raw_usage, Mapping) else {}
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.HTTPError) as exc:
        error = f"{type(exc).__name__}: {exc}"[:1000]
    elapsed_ms = (time.monotonic() - started) * 1000
    return {
        "schema_version": SCHEMA_VERSION,
        "id": _candidate_id(task_id, model, max_tokens, None if runtime_id == "legacy" else runtime_id),
        "task_id": task_id,
        "task_text": task_text,
        "functiongemma_assessment": dict(assessment),
        "engine": "gemma_e2b",
        "engine_version": "gemma-4-e2b-litert-lm-v1",
        "prompt_version": E2B_PROMPT_VERSION,
        "model_id": model,
        "generation_limit_tokens": max_tokens,
        "runtime_id": runtime_id,
        "answer": answer,
        "latency_ms": elapsed_ms,
        "failure": bool(error),
        "error": error,
        "local_tokens": {
            "prompt": _non_negative_int(usage.get("prompt_tokens")),
            "completion": _non_negative_int(usage.get("completion_tokens")),
        },
        "fireworks_tokens": {"prompt": 0, "completion": 0},
    }


def _candidate_id(task_id: str, model: str, max_tokens: int, runtime_id: str | None = None) -> str:
    parts = [task_id, model, str(max_tokens)]
    if runtime_id is not None:
        parts.append(runtime_id)
    digest = hashlib.sha256("\0".join(parts).encode()).hexdigest()[:20]
    return f"candidate_{digest}"


def _assessment_index(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        task_id = row.get("id")
        assessment = row.get("prediction")
        if not isinstance(task_id, str) or not task_id or not isinstance(assessment, Mapping):
            continue
        if task_id in result:
            raise ValueError(f"Duplicate assessment id {task_id!r}.")
        result[task_id] = assessment
    return result


def _task(row: Mapping[str, Any]) -> tuple[str, str]:
    task_id = row.get("id")
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("Task row requires a non-empty id.")
    input_text = row.get("input_text")
    if isinstance(input_text, str) and input_text.strip():
        return task_id, input_text.strip()
    messages = row.get("messages")
    if isinstance(messages, list):
        users = [message.get("content") for message in messages if isinstance(message, Mapping) and message.get("role") == "user"]
        if len(users) == 1 and isinstance(users[0], str) and users[0].strip():
            return task_id, users[0].strip()
    raise ValueError(f"Task {task_id!r} has no canonical input text.")


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_number} must be a JSON object.")
        rows.append(payload)
    return rows


def _non_negative_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
