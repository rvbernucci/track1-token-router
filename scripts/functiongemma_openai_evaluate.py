#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from router.core.contracts import TaskAssessment
from router.functiongemma.metrics import assessment_metrics
from router.functiongemma.tooling import (
    ASSESS_TASK_TOOL,
    DEVELOPER_INSTRUCTION,
    assessment_from_function_call,
    file_sha256,
    jsonl_rows,
    validate_training_row,
)
from scripts.functiongemma_experiment import percentile, write_json


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Evaluate FunctionGemma through an OpenAI-compatible server.")
    value.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    value.add_argument("--model", required=True)
    value.add_argument("--tasks", type=Path, required=True)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--report", type=Path, required=True)
    value.add_argument("--max-tokens", type=int, default=160)
    value.add_argument("--timeout-s", type=float, default=20.0)
    value.add_argument("--resume", action="store_true")
    return value


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    result = evaluate(
        base_url=args.base_url,
        model=args.model,
        tasks_path=args.tasks,
        output=args.output,
        report_path=args.report,
        max_tokens=args.max_tokens,
        timeout_s=args.timeout_s,
        resume=args.resume,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def evaluate(
    *,
    base_url: str,
    model: str,
    tasks_path: Path,
    output: Path,
    report_path: Path,
    max_tokens: int,
    timeout_s: float,
    resume: bool = False,
) -> dict[str, Any]:
    if not 1 <= max_tokens <= 256:
        raise ValueError("max_tokens must be in [1, 256].")
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive.")
    tasks = jsonl_rows(tasks_path)
    if not resume and output.exists():
        output.unlink()
    existing = jsonl_rows(output) if output.exists() else []
    completed = {str(row.get("id") or "") for row in existing}
    if "" in completed or len(completed) != len(existing):
        raise ValueError("Existing resumable predictions require unique non-empty ids.")
    output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with output.open("a", encoding="utf-8") as handle:
        for row in tasks:
            example_id, task_text = _task(row)
            if example_id in completed:
                continue
            gold = validate_training_row(row).to_dict()
            started = time.monotonic()
            response: Mapping[str, Any] | None = None
            prediction: dict[str, Any] | None = None
            error: str | None = None
            try:
                response = request_assessment(
                    base_url=base_url,
                    model=model,
                    task_text=task_text,
                    max_tokens=max_tokens,
                    timeout_s=timeout_s,
                )
                prediction = assessment_from_openai_response(response).to_dict()
            except (OSError, TimeoutError, ValueError, urllib.error.URLError) as exc:
                error = str(exc)
            latency = (time.monotonic() - started) * 1000
            usage = response.get("usage", {}) if isinstance(response, Mapping) else {}
            prediction_row = {
                "id": example_id,
                "gold": gold,
                "prediction": prediction,
                "raw_message": _response_message(response),
                "parse_error": error,
                "latency_ms": latency,
                "input_tokens": _usage_integer(usage, "prompt_tokens"),
                "output_tokens": _usage_integer(usage, "completion_tokens"),
            }
            handle.write(json.dumps(prediction_row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            completed.add(example_id)
            written += 1
    predictions = jsonl_rows(output)
    task_ids = {str(row["id"]) for row in tasks}
    if {str(row["id"]) for row in predictions} != task_ids:
        raise ValueError("Prediction output does not cover exactly the requested tasks.")
    latencies = [float(row["latency_ms"]) for row in predictions]
    metrics = assessment_metrics(predictions)
    metrics.update(
        {
            "model": model,
            "base_url": base_url,
            "p50_latency_ms": percentile(latencies, 0.50),
            "p95_latency_ms": percentile(latencies, 0.95),
            "predictions_sha256": file_sha256(output),
            "resumed": resume,
            "already_complete": len(existing),
            "written": written,
        }
    )
    write_json(report_path, metrics)
    return metrics


def request_assessment(
    *,
    base_url: str,
    model: str,
    task_text: str,
    max_tokens: int,
    timeout_s: float,
) -> Mapping[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {"role": "developer", "content": DEVELOPER_INSTRUCTION},
            {"role": "user", "content": task_text},
        ],
        "tools": [ASSESS_TASK_TOOL],
        "tool_choice": "required",
        "temperature": 0,
        "max_tokens": max_tokens,
        "stop": ["<end_function_call>"],
    }
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("FUNCTIONGEMMA_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as result:
        response = json.load(result)
    if not isinstance(response, Mapping):
        raise ValueError("OpenAI-compatible response must be an object.")
    return response


def assessment_from_openai_response(payload: Mapping[str, Any]) -> TaskAssessment:
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
        raise ValueError("Assessment response must contain exactly one choice.")
    message = choices[0].get("message")
    if not isinstance(message, Mapping):
        raise ValueError("Assessment response choice is missing its message.")
    calls = message.get("tool_calls")
    if isinstance(calls, list) and calls:
        if len(calls) != 1 or not isinstance(calls[0], Mapping):
            raise ValueError("Assessment response must contain exactly one tool call.")
        function = calls[0].get("function")
        if not isinstance(function, Mapping) or function.get("name") != "assess_task":
            raise ValueError("Assessment response called an unexpected function.")
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        if not isinstance(arguments, Mapping):
            raise ValueError("Assessment tool arguments must be an object.")
        return TaskAssessment.from_mapping(arguments)
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("Assessment response has neither a tool call nor native-call content.")
    if content.startswith("<start_function_call>") and "<end_function_call>" not in content:
        content += "<end_function_call>"
    return assessment_from_function_call(content)


def _response_message(payload: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
        return None
    message = choices[0].get("message")
    return dict(message) if isinstance(message, Mapping) else None


def _task(row: Mapping[str, Any]) -> tuple[str, str]:
    messages = row.get("messages")
    if not isinstance(messages, list) or len(messages) < 2 or not isinstance(messages[1], Mapping):
        raise ValueError("Evaluation task has no input text.")
    return str(row["id"]), str(messages[1]["content"])


def _usage_integer(payload: Any, name: str) -> int | None:
    value = payload.get(name) if isinstance(payload, Mapping) else None
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


if __name__ == "__main__":
    raise SystemExit(main())
