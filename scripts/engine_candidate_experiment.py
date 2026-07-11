#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from router.core.contracts import TaskEnvelope
from router.core.fireworks import FireworksClient
from router.core.model_client import ModelClientError
from router.core.prompts import (
    ANSWER_PROMPT_VERSION,
    CONCISE_ANSWER_PROMPT_VERSION,
    CONCISE_ANSWER_SYSTEM_PROMPT,
    build_answer_messages,
)
from router.core.fireworks_runner import _completion_token_policy
from router.functiongemma.tooling import jsonl_rows
from router.orchestration.fireworks_model_router import (
    _profile_for_model,
    normalize_fireworks_model_id,
    select_fireworks_model,
    select_reasoning_effort,
)
from router.orchestration.solvers import solve_deterministic


SCHEMA_VERSION = "engine-answer-candidate-v1"
PROMPT_VERSION = ANSWER_PROMPT_VERSION
SYSTEM_PROMPT = ""


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Collect resumable answer candidates for an outcome matrix.")
    root.add_argument("--tasks", type=Path, required=True)
    root.add_argument("--assessments", type=Path, required=True)
    root.add_argument("--output", type=Path, required=True)
    root.add_argument("--engine", choices=["deterministic", "fireworks"], required=True)
    root.add_argument("--model")
    root.add_argument("--base-url", default=os.getenv("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"))
    root.add_argument("--max-tokens", type=int, default=384)
    root.add_argument("--timeout-s", type=float, default=60.0)
    root.add_argument("--budget-usd", type=float, default=0.0)
    root.add_argument("--runtime-token-policy", action="store_true")
    root.add_argument("--prompt-mode", choices=["raw", "concise"], default="raw")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    client = None
    model = normalize_fireworks_model_id(args.model)
    if args.engine == "fireworks":
        api_key = os.getenv("FIREWORKS_API_KEY")
        if not api_key:
            raise SystemExit("FIREWORKS_API_KEY is not set.")
        if not model:
            raise SystemExit("--model is required for the Fireworks engine.")
        client = FireworksClient(
            base_url=args.base_url,
            model=model,
            api_key=api_key,
            timeout_s=args.timeout_s,
            max_retries=0,
        )
    result = run_experiment(
        tasks_path=args.tasks,
        assessments_path=args.assessments,
        output=args.output,
        engine=args.engine,
        model=model or None,
        client=client,
        max_tokens=args.max_tokens,
        budget_usd=args.budget_usd,
        runtime_token_policy=args.runtime_token_policy,
        prompt_mode=args.prompt_mode,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def run_experiment(
    *,
    tasks_path: Path,
    assessments_path: Path,
    output: Path,
    engine: str,
    model: str | None,
    client: Any,
    max_tokens: int,
    budget_usd: float,
    runtime_token_policy: bool = False,
    prompt_mode: str = "raw",
) -> dict[str, Any]:
    if engine not in {"deterministic", "fireworks"}:
        raise ValueError("Unsupported engine.")
    if max_tokens < 1 or budget_usd < 0:
        raise ValueError("max_tokens must be positive and budget_usd non-negative.")
    if engine == "fireworks" and (client is None or not model):
        raise ValueError("Fireworks collection requires a client and model.")
    prompt_version = _prompt_version(prompt_mode)
    tasks = [_task(row) for row in jsonl_rows(tasks_path)]
    assessments = _assessment_index(jsonl_rows(assessments_path))
    existing_rows = jsonl_rows(output) if output.exists() else []
    completed = {str(row.get("id")) for row in existing_rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    spent_before = sum(
        float(row.get("billable_cost_usd") or 0.0)
        for row in existing_rows
        if row.get("model_id") == model
    )
    spent = 0.0
    written = 0
    stopped_for_budget = False
    with output.open("a", encoding="utf-8") as handle:
        for task_id, task_text in tasks:
            task_limit = max_tokens
            request_options: dict[str, Any] = {"reasoning_effort": "none", "user": "track1-outcome-matrix-v1"}
            if engine == "fireworks" and runtime_token_policy:
                envelope = TaskEnvelope(id=task_id, input_text=task_text)
                selection = select_fireworks_model(envelope, [model or ""], default_model=model or "")
                task_limit = int(_completion_token_policy(
                    envelope,
                    tier=selection.tier,
                    domain=selection.domain,
                    configured_max_tokens=max_tokens,
                )["max_tokens"])
                request_options = {"user": "track1-token-router-v1"}
                reasoning_effort = select_reasoning_effort(model or "", selection.tier)
                if reasoning_effort:
                    request_options["reasoning_effort"] = reasoning_effort
            candidate_id = _candidate_id(task_id, engine, model, task_limit, prompt_version=prompt_version)
            if candidate_id in completed:
                continue
            if engine == "fireworks":
                upper = _upper_bound_cost(model or "", task_text, task_limit, prompt_mode=prompt_mode)
                if spent_before + spent + upper > budget_usd + 1e-12:
                    stopped_for_budget = True
                    break
                row = _fireworks_candidate(
                    task_id=task_id,
                    task_text=task_text,
                    assessment=assessments.get(task_id),
                    candidate_id=candidate_id,
                    model=model or "",
                    client=client,
                    max_tokens=task_limit,
                    request_options=request_options,
                    prompt_mode=prompt_mode,
                    prompt_version=prompt_version,
                )
                spent += float(row["billable_cost_usd"])
                if spent > budget_usd + 1e-12:
                    raise RuntimeError("Observed Fireworks spend exceeded the explicit budget.")
            else:
                row = _deterministic_candidate(
                    task_id=task_id,
                    task_text=task_text,
                    assessment=assessments.get(task_id),
                    candidate_id=candidate_id,
                )
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            completed.add(candidate_id)
            written += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": engine,
        "model": model,
        "tasks": len(tasks),
        "written": written,
        "completed": len(completed),
        "billable_cost_usd": spent,
        "cumulative_billable_cost_usd": spent_before + spent,
        "budget_usd": budget_usd,
        "stopped_for_budget": stopped_for_budget,
        "runtime_token_policy": runtime_token_policy,
        "prompt_mode": prompt_mode,
        "prompt_version": prompt_version if engine == "fireworks" else None,
    }


def _fireworks_candidate(
    *,
    task_id: str,
    task_text: str,
    assessment: Mapping[str, Any] | None,
    candidate_id: str,
    model: str,
    client: Any,
    max_tokens: int,
    request_options: Mapping[str, Any],
    prompt_mode: str,
    prompt_version: str,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        response = client.complete(
            build_answer_messages(TaskEnvelope(id=task_id, input_text=task_text), mode=prompt_mode),
            temperature=0.0,
            max_tokens=max_tokens,
            extra_body=dict(request_options),
        )
        latency_ms = (time.monotonic() - started) * 1000
        status = "answered" if response.text.strip() else "runtime_failure"
        usage = response.usage
        cost = _usage_cost(model, usage.prompt, usage.completion)
        return _candidate_row(
            candidate_id=candidate_id,
            task_id=task_id,
            task_text=task_text,
            assessment=assessment,
            engine="fireworks",
            engine_version=f"fireworks-openai-{prompt_version}",
            model_id=model,
            answer=response.text.strip(),
            status=status,
            latency_ms=latency_ms,
            prompt_tokens=usage.prompt,
            completion_tokens=usage.completion,
            max_tokens=max_tokens,
            billable_cost_usd=cost,
            error="" if status == "answered" else "empty_answer",
            request_options=request_options,
            prompt_version=prompt_version,
        )
    except ModelClientError as exc:
        return _candidate_row(
            candidate_id=candidate_id,
            task_id=task_id,
            task_text=task_text,
            assessment=assessment,
            engine="fireworks",
            engine_version=f"fireworks-openai-{prompt_version}",
            model_id=model,
            answer="",
            status="runtime_failure",
            latency_ms=(time.monotonic() - started) * 1000,
            prompt_tokens=0,
            completion_tokens=0,
            max_tokens=max_tokens,
            billable_cost_usd=0.0,
            error=str(exc),
            request_options=request_options,
            prompt_version=prompt_version,
        )


def _deterministic_candidate(
    *, task_id: str, task_text: str, assessment: Mapping[str, Any] | None, candidate_id: str
) -> dict[str, Any]:
    started = time.monotonic()
    result = solve_deterministic(TaskEnvelope(id=task_id, input_text=task_text))
    latency_ms = (time.monotonic() - started) * 1000
    return _candidate_row(
        candidate_id=candidate_id,
        task_id=task_id,
        task_text=task_text,
        assessment=assessment,
        engine="deterministic",
        engine_version="solver-manifest-v1",
        model_id=None,
        answer=result.answer if result else "",
        status="answered" if result else "refused",
        latency_ms=latency_ms,
        prompt_tokens=0,
        completion_tokens=0,
        max_tokens=0,
        billable_cost_usd=0.0,
        error="" if result else "no_registered_solver_accepted",
        solver_name=result.solver_name if result else None,
    )


def _candidate_row(
    *,
    candidate_id: str,
    task_id: str,
    task_text: str,
    assessment: Mapping[str, Any] | None,
    engine: str,
    engine_version: str,
    model_id: str | None,
    answer: str,
    status: str,
    latency_ms: float,
    prompt_tokens: int,
    completion_tokens: int,
    max_tokens: int,
    billable_cost_usd: float,
    error: str,
    solver_name: str | None = None,
    request_options: Mapping[str, Any] | None = None,
    prompt_version: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "id": candidate_id,
        "task_id": task_id,
        "task_text": task_text,
        "functiongemma_assessment": assessment,
        "engine": engine,
        "engine_version": engine_version,
        "model_id": model_id,
        "prompt_version": prompt_version if engine == "fireworks" else None,
        "solver_name": solver_name,
        "answer": answer,
        "status": status,
        "refusal": status == "refused",
        "failure": status == "runtime_failure",
        "error": error,
        "latency_ms": latency_ms,
        "generation_limit_tokens": max_tokens,
        "fireworks_tokens": {"prompt": prompt_tokens, "completion": completion_tokens},
        "local_tokens": {"prompt": 0, "completion": 0},
        "billable_cost_usd": billable_cost_usd,
        "request_options": dict(request_options or {}),
    }


def _task(row: Mapping[str, Any]) -> tuple[str, str]:
    messages = row.get("messages")
    if not isinstance(messages, list) or len(messages) < 2 or not isinstance(messages[1], Mapping):
        raise ValueError("Task row has no user message.")
    return str(row["id"]), str(messages[1]["content"])


def _assessment_index(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result = {}
    for row in rows:
        prediction = row.get("prediction")
        if isinstance(prediction, Mapping):
            result[str(row["id"])] = prediction
    return result


def _candidate_id(
    task_id: str,
    engine: str,
    model: str | None,
    max_tokens: int,
    *,
    prompt_version: str = PROMPT_VERSION,
) -> str:
    raw = f"{task_id}\0{engine}\0{model or ''}\0{max_tokens}\0{prompt_version}"
    return "candidate_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _upper_bound_cost(model: str, task_text: str, max_tokens: int, *, prompt_mode: str = "raw") -> float:
    system_prompt = CONCISE_ANSWER_SYSTEM_PROMPT if prompt_mode == "concise" else SYSTEM_PROMPT
    prompt_tokens = max(1, (len(system_prompt.encode("utf-8")) + len(task_text.encode("utf-8")) + 3) // 4)
    return _usage_cost(model, prompt_tokens, max_tokens)


def _prompt_version(prompt_mode: str) -> str:
    if prompt_mode == "raw":
        return ANSWER_PROMPT_VERSION
    if prompt_mode == "concise":
        return CONCISE_ANSWER_PROMPT_VERSION
    raise ValueError(f"Unknown prompt mode {prompt_mode!r}.")


def _usage_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    profile = _profile_for_model(model)
    return (
        prompt_tokens * profile.input_price_per_mtok + completion_tokens * profile.output_price_per_mtok
    ) / 1_000_000


if __name__ == "__main__":
    raise SystemExit(main())
