#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import AnswerResult, TaskEnvelope, TokenUsage
from router.core.fireworks import FireworksClient
from router.core.fireworks_runner import FireworksDirectRunner
from router.orchestration.fireworks_model_router import _profile_for_model, normalize_fireworks_model_id
from scripts.fireworks_microbench import BenchTask, _load_env_files, _load_tasks, _validate


DEFAULT_BASE_URL = "https://api.fireworks.ai/inference/v1"
DEFAULT_DATASETS = (Path("evals/fireworks-pareto/escape-microbench.jsonl"),)
DEFAULT_ENV_FILES = (Path(".env.fireworks"), Path(".env.fireworks.local"))
DEFAULT_OUTPUT_JSONL = Path("reports/generated/fireworks-runtime-eval-results.jsonl")
DEFAULT_REPORT = Path("reports/generated/fireworks-runtime-eval-report.md")
DEFAULT_MATRIX_WEIGHTS = Path("router/data/fireworks_track1_allowed_weights.json")
DEFAULT_ALLOWED_MODELS = [
    "accounts/fireworks/models/minimax-m3",
    "accounts/fireworks/models/kimi-k2p7-code",
    "accounts/fireworks/models/gemma-4-31b-it",
    "accounts/fireworks/models/gemma-4-26b-a4b-it",
    "accounts/fireworks/models/gemma-4-31b-it-nvfp4",
]


@dataclass(frozen=True)
class RuntimeEvalConfig:
    datasets: tuple[Path, ...]
    allowed_models: list[str]
    base_url: str
    api_key: str
    output_jsonl: Path
    report: Path
    temperature: float
    max_tokens: int
    timeout_s: float
    max_retries: int
    max_tasks: int
    budget_usd: float
    matrix_weights_path: Path | None
    progress_every: int = 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the full Fireworks runtime router on benchmark tasks.")
    parser.add_argument("--dataset", action="append", type=Path, help="Benchmark JSONL dataset. Can be passed more than once.")
    parser.add_argument("--allowed-models", help="CSV, whitespace-separated, or JSON list of allowed model IDs.")
    parser.add_argument("--base-url")
    parser.add_argument("--env-file", action="append", type=Path, help="Load KEY=VALUE pairs before running.")
    parser.add_argument("--output-jsonl", type=Path, default=DEFAULT_OUTPUT_JSONL)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=256, help="Global cap; runtime may use a smaller dynamic cap.")
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--max-retries", type=int, default=0)
    parser.add_argument("--max-tasks", type=int, default=24, help="Maximum tasks to evaluate; <=0 means all loaded tasks.")
    parser.add_argument("--budget-usd", type=float, default=0.25)
    parser.add_argument("--matrix-weights", type=Path, default=DEFAULT_MATRIX_WEIGHTS)
    parser.add_argument("--no-matrix-weights", action="store_true")
    parser.add_argument("--progress-every", type=int, default=0, help="Print progress to stderr every N tasks.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print compact JSON summary.")
    args = parser.parse_args()

    _load_env_files(tuple(args.env_file or DEFAULT_ENV_FILES))
    api_key = os.getenv("FIREWORKS_API_KEY", "")
    datasets = tuple(args.dataset or DEFAULT_DATASETS)
    tasks = _limit_tasks(_load_all_tasks(datasets), args.max_tasks)
    allowed_models = _parse_allowed_models(args.allowed_models or os.getenv("ALLOWED_MODELS")) or DEFAULT_ALLOWED_MODELS
    matrix_weights = None if args.no_matrix_weights else args.matrix_weights
    if matrix_weights is not None and not matrix_weights.exists():
        matrix_weights = None

    plan_summary = {
        "datasets": [str(path) for path in datasets],
        "tasks": len(tasks),
        "allowed_models": allowed_models,
        "budget_usd": args.budget_usd,
        "estimated_upper_cost_usd": round(_estimated_upper_cost(tasks, allowed_models, args.max_tokens), 8),
        "matrix_weights": str(matrix_weights) if matrix_weights else "",
        "max_tokens_global": args.max_tokens,
    }
    if args.dry_run:
        _print_summary({"dry_run": True, **plan_summary}, args.json)
        return 0
    if not api_key:
        print("FIREWORKS_API_KEY is not set. This script never prints FIREWORKS_API_KEY.", file=sys.stderr)
        return 2

    config = RuntimeEvalConfig(
        datasets=datasets,
        allowed_models=allowed_models,
        base_url=args.base_url or os.getenv("FIREWORKS_BASE_URL") or DEFAULT_BASE_URL,
        api_key=api_key,
        output_jsonl=args.output_jsonl,
        report=args.report,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout_s=args.timeout_s,
        max_retries=args.max_retries,
        max_tasks=args.max_tasks,
        budget_usd=args.budget_usd,
        matrix_weights_path=matrix_weights,
        progress_every=args.progress_every,
    )
    rows = run_runtime_eval(config, tasks)
    summary = summarize(rows)
    summary.update(
        {
            "output_jsonl": str(config.output_jsonl),
            "report": str(config.report),
            "budget_usd": config.budget_usd,
        }
    )
    config.report.parent.mkdir(parents=True, exist_ok=True)
    config.report.write_text(render_report(rows, config, summary), encoding="utf-8")
    _print_summary(summary, args.json)
    return 0


def run_runtime_eval(config: RuntimeEvalConfig, tasks: list[BenchTask]) -> list[dict[str, Any]]:
    client = FireworksClient(
        base_url=config.base_url,
        model=config.allowed_models[0],
        api_key=config.api_key,
        timeout_s=config.timeout_s,
        max_retries=config.max_retries,
    )
    runner = FireworksDirectRunner(
        client,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        allowed_models=config.allowed_models,
        matrix_weights_path=config.matrix_weights_path,
    )

    config.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    spent = 0.0
    with config.output_jsonl.open("w", encoding="utf-8") as handle:
        for task in tasks:
            if rows and spent >= config.budget_usd:
                break
            started_at = perf_counter()
            result = runner.run(
                TaskEnvelope(
                    id=task.id,
                    input_text=task.prompt,
                    metadata={"domain": task.domain, "tier": task.tier, "validator": task.validator},
                )
            )
            row = _row_from_result(task, result, elapsed_ms=_elapsed_ms(started_at))
            spent += float(row["estimated_cost_usd"])
            rows.append(row)
            handle.write(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n")
            handle.flush()
            if config.progress_every > 0 and len(rows) % config.progress_every == 0:
                print(
                    json.dumps(
                        {
                            "completed": len(rows),
                            "valid": sum(1 for item in rows if item.get("valid")),
                            "remote_tokens": sum(int(item.get("remote_tokens", {}).get("total") or 0) for item in rows),
                            "estimated_cost_usd": round(spent, 8),
                            "last_task": task.id,
                            "last_route": result.route,
                        },
                        ensure_ascii=True,
                        separators=(",", ":"),
                    ),
                    file=sys.stderr,
                )
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    route_counts = _count_by(rows, "route")
    model_counts = _count_by(rows, "fireworks_model")
    domain_summary: dict[str, dict[str, Any]] = {}
    format_summary: dict[str, dict[str, Any]] = {}
    for row in rows:
        _add_summary_row(domain_summary.setdefault(str(row["domain"]), _empty_group()), row)
        policy = row.get("fireworks_completion_token_policy")
        expected_format = str(policy.get("expected_format") if isinstance(policy, dict) else "local_or_unknown")
        _add_summary_row(format_summary.setdefault(expected_format, _empty_group()), row)
    _finish_groups(domain_summary)
    _finish_groups(format_summary)
    remote_tokens = {
        "prompt": sum(int(row.get("remote_tokens", {}).get("prompt") or 0) for row in rows),
        "completion": sum(int(row.get("remote_tokens", {}).get("completion") or 0) for row in rows),
        "total": sum(int(row.get("remote_tokens", {}).get("total") or 0) for row in rows),
    }
    calls = len(rows)
    valid = sum(1 for row in rows if row.get("valid"))
    return {
        "tasks": calls,
        "valid": valid,
        "valid_rate": valid / calls if calls else 0.0,
        "fireworks_tasks": sum(1 for row in rows if int(row.get("remote_tokens", {}).get("total") or 0) > 0),
        "zero_remote_token_tasks": sum(1 for row in rows if int(row.get("remote_tokens", {}).get("total") or 0) == 0),
        "remote_tokens": remote_tokens,
        "estimated_cost_usd": round(sum(float(row.get("estimated_cost_usd") or 0.0) for row in rows), 8),
        "invalid_attempts": sum(len(row.get("fireworks_invalid_attempts") or []) for row in rows),
        "route_counts": route_counts,
        "fireworks_model_counts": model_counts,
        "domain_summary": domain_summary,
        "expected_format_summary": format_summary,
    }


def render_report(rows: list[dict[str, Any]], config: RuntimeEvalConfig, summary: dict[str, Any]) -> str:
    lines = [
        "# Fireworks Runtime Router Eval",
        "",
        f"- datasets: `{', '.join(str(path) for path in config.datasets)}`",
        f"- tasks: `{summary['tasks']}`",
        f"- valid_rate: `{summary['valid_rate']:.2f}`",
        f"- remote_tokens_total: `{summary['remote_tokens']['total']}`",
        f"- estimated_cost_usd: `{summary['estimated_cost_usd']:.8f}`",
        f"- matrix_weights: `{config.matrix_weights_path or ''}`",
        f"- global_max_tokens: `{config.max_tokens}`",
        "",
        "## Route Summary",
        "",
        "| Route | Tasks |",
        "| --- | ---: |",
    ]
    for route, count in sorted(summary["route_counts"].items()):
        lines.append(f"| `{route}` | {count} |")
    lines.extend(["", "## Fireworks Model Summary", "", "| Model | Tasks |", "| --- | ---: |"])
    for model, count in sorted(summary["fireworks_model_counts"].items()):
        lines.append(f"| `{model}` | {count} |")
    lines.extend(["", "## Domain Summary", ""])
    lines.extend(_group_table(summary["domain_summary"], "Domain"))
    lines.extend(["", "## Expected Format Summary", ""])
    lines.extend(_group_table(summary["expected_format_summary"], "Expected Format"))
    lines.extend(["", "## Failed Cases", ""])
    failed = [row for row in rows if not row.get("valid")]
    if not failed:
        lines.append("- none")
    for row in failed:
        lines.append(
            f"- `{row['id']}` / `{row['domain']}` / `{row['route']}` / `{row.get('fireworks_model') or 'local'}`: "
            f"{row.get('validation_reason')}"
        )
    lines.extend(["", "## Invalid Fireworks Attempts", ""])
    invalid_rows = [row for row in rows if row.get("fireworks_invalid_attempts")]
    if not invalid_rows:
        lines.append("- none")
    for row in invalid_rows:
        lines.append(f"- `{row['id']}`: `{json.dumps(row['fireworks_invalid_attempts'], ensure_ascii=True)}`")
    lines.append("")
    return "\n".join(lines)


def _row_from_result(task: BenchTask, result: AnswerResult, *, elapsed_ms: int) -> dict[str, Any]:
    validation = _validate(task.validator, result.answer)
    metadata = result.metadata
    model = str(metadata.get("fireworks_model") or "")
    matrix_selection = metadata.get("fireworks_matrix_selection")
    token_policy = metadata.get("fireworks_completion_token_policy")
    invalid_attempts = list(metadata.get("fireworks_invalid_attempts") or [])
    return {
        "id": task.id,
        "domain": task.domain,
        "tier": task.tier,
        "route": result.route,
        "valid": validation["valid"],
        "validation_reason": validation["reason"],
        "answer_preview": _truncate(result.answer.strip(), 240),
        "remote_tokens": result.remote_tokens.to_dict(),
        "estimated_cost_usd": _estimate_result_cost(result),
        "elapsed_ms": elapsed_ms,
        "fireworks_latency_ms": int(metadata.get("latency_fireworks_ms") or 0),
        "fireworks_model": model,
        "fireworks_matrix_model": _matrix_model(matrix_selection),
        "fireworks_ranked_candidates": _ranked_candidates(matrix_selection),
        "fireworks_model_selection": _compact_model_selection(metadata.get("fireworks_model_selection")),
        "fireworks_completion_token_policy": token_policy if isinstance(token_policy, dict) else {},
        "fireworks_request_options": metadata.get("fireworks_request_options") or {},
        "fireworks_invalid_attempts": invalid_attempts,
        "fireworks_attempt_errors": metadata.get("fireworks_attempt_errors") or [],
        "final_validation": metadata.get("final_validation") or {},
    }


def _estimate_result_cost(result: AnswerResult) -> float:
    total_usage = result.remote_tokens
    if total_usage.total <= 0:
        return 0.0
    metadata = result.metadata
    invalid_attempts = list(metadata.get("fireworks_invalid_attempts") or [])
    invalid_usage = TokenUsage.empty()
    cost = 0.0
    for attempt in invalid_attempts:
        if not isinstance(attempt, dict):
            continue
        model = str(attempt.get("model") or "")
        usage = _usage_from_mapping(attempt.get("usage"))
        invalid_usage = _add_usage(invalid_usage, usage)
        cost += _usage_cost(model, usage)
    final_usage = TokenUsage(
        prompt=max(0, total_usage.prompt - invalid_usage.prompt),
        completion=max(0, total_usage.completion - invalid_usage.completion),
        total=max(0, total_usage.total - invalid_usage.total),
    )
    cost += _usage_cost(str(metadata.get("fireworks_model") or ""), final_usage)
    return round(cost, 10)


def _usage_cost(model: str, usage: TokenUsage) -> float:
    if usage.total <= 0:
        return 0.0
    profile = _profile_for_model(model)
    return (
        (usage.prompt * profile.input_price_per_mtok)
        + (usage.completion * profile.output_price_per_mtok)
    ) / 1_000_000


def _usage_from_mapping(value: object) -> TokenUsage:
    if not isinstance(value, dict):
        return TokenUsage.empty()
    return TokenUsage(
        prompt=int(value.get("prompt") or 0),
        completion=int(value.get("completion") or 0),
        total=int(value.get("total") or 0),
    )


def _add_usage(left: TokenUsage, right: TokenUsage) -> TokenUsage:
    return TokenUsage(
        prompt=left.prompt + right.prompt,
        completion=left.completion + right.completion,
        total=left.total + right.total,
    )


def _load_all_tasks(paths: tuple[Path, ...]) -> list[BenchTask]:
    tasks: list[BenchTask] = []
    seen: set[str] = set()
    for path in paths:
        for task in _load_tasks(path):
            if task.id in seen:
                continue
            tasks.append(task)
            seen.add(task.id)
    if not tasks:
        raise ValueError("No runtime eval tasks loaded.")
    return tasks


def _limit_tasks(tasks: list[BenchTask], max_tasks: int) -> list[BenchTask]:
    if max_tasks <= 0:
        return tasks
    return tasks[:max_tasks]


def _parse_allowed_models(raw: str | None) -> list[str]:
    if not raw:
        return []
    stripped = raw.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, list):
            return [normalize_fireworks_model_id(str(item)) for item in payload if str(item).strip()]
    return [normalize_fireworks_model_id(item) for item in re.split(r"[,\s]+", stripped) if item.strip()]


def _estimated_upper_cost(tasks: list[BenchTask], models: list[str], max_tokens: int) -> float:
    total = 0.0
    for task in tasks:
        prompt_tokens = max(1, len(task.prompt) // 4 + 1)
        for model in models[: max(1, min(3, len(models)))]:
            profile = _profile_for_model(model)
            total += ((prompt_tokens * profile.input_price_per_mtok) + (max_tokens * profile.output_price_per_mtok)) / 1_000_000
    return total


def _matrix_model(matrix_selection: object) -> str:
    if isinstance(matrix_selection, dict):
        return str(matrix_selection.get("model") or "")
    return ""


def _ranked_candidates(matrix_selection: object) -> list[dict[str, object]]:
    if not isinstance(matrix_selection, dict):
        return []
    ranked = matrix_selection.get("ranked_candidates")
    if not isinstance(ranked, list):
        return []
    compact = []
    for candidate in ranked[:5]:
        if not isinstance(candidate, dict):
            continue
        compact.append(
            {
                "model": candidate.get("model"),
                "hybrid_score": candidate.get("hybrid_score"),
                "predicted_utility": candidate.get("predicted_utility"),
                "nash_product": candidate.get("nash_product"),
                "observed_valid_rate": candidate.get("observed_valid_rate"),
                "observed_avg_total_tokens": candidate.get("observed_avg_total_tokens"),
            }
        )
    return compact


def _compact_model_selection(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {
        "model": value.get("model"),
        "tier": value.get("tier"),
        "domain": value.get("domain"),
        "reason": value.get("reason"),
        "pareto_frontier": value.get("pareto_frontier"),
        "game_theory": value.get("game_theory"),
    }


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "local_or_none")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _empty_group() -> dict[str, Any]:
    return {"tasks": 0, "valid": 0, "remote_tokens": 0, "cost": 0.0, "latency_ms": 0}


def _add_summary_row(group: dict[str, Any], row: dict[str, Any]) -> None:
    group["tasks"] += 1
    group["valid"] += 1 if row.get("valid") else 0
    group["remote_tokens"] += int(row.get("remote_tokens", {}).get("total") or 0)
    group["cost"] += float(row.get("estimated_cost_usd") or 0.0)
    group["latency_ms"] += int(row.get("elapsed_ms") or 0)


def _finish_groups(groups: dict[str, dict[str, Any]]) -> None:
    for group in groups.values():
        tasks = max(int(group["tasks"]), 1)
        group["valid_rate"] = group["valid"] / tasks
        group["avg_remote_tokens"] = group["remote_tokens"] / tasks
        group["avg_latency_ms"] = group["latency_ms"] / tasks
        group["cost"] = round(float(group["cost"]), 10)


def _group_table(groups: dict[str, dict[str, Any]], label: str) -> list[str]:
    lines = [
        f"| {label} | Tasks | Valid | Valid Rate | Remote Tokens | Avg Remote Tokens | Cost USD | Avg Latency ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, group in sorted(groups.items()):
        lines.append(
            f"| `{name}` | {group['tasks']} | {group['valid']} | {group['valid_rate']:.2f} "
            f"| {group['remote_tokens']} | {group['avg_remote_tokens']:.1f} "
            f"| {group['cost']:.8f} | {group['avg_latency_ms']:.0f} |"
        )
    return lines


def _elapsed_ms(started_at: float) -> int:
    return round((perf_counter() - started_at) * 1000)


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[:limit] + "...[truncated]"


def _print_summary(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
    else:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
