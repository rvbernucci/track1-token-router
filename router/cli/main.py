from __future__ import annotations

import argparse
import json
import os
import resource
import sys
from pathlib import Path
from time import perf_counter
from typing import Sequence

from router.adapters.official import get_adapter
from router.adapters.io import load_jsonl_tasks, parse_json_task, task_from_text, write_jsonl_results
from router.core.config import RouterConfig
from router.core.contracts import AnswerResult, TaskEnvelope
from router.core.logging import JsonlRunLogger
from router.core.runner import TaskRunner
from router.core.runner_factory import build_runner
from router.orchestration.final_validator import finalize_answer_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="router",
        description="CLI-first hybrid token router for AMD Developer Hackathon Track 1.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask = subparsers.add_parser("ask", help="Run one plain-text task.")
    ask.add_argument("text", nargs="?", help="Task text. If omitted, stdin is used.")
    ask.add_argument("--file", type=Path, help="Read task text from a file.")
    ask.add_argument("--id", dest="task_id", help="Optional task id.")
    ask.add_argument("--json", action="store_true", help="Print full AnswerResult JSON.")

    solve = subparsers.add_parser("solve", help="Run one JSON task from stdin.")
    solve.add_argument("--json", action="store_true", help="Read JSON task from stdin and print JSON result.")

    run = subparsers.add_parser("run", help="Run a JSONL task file.")
    run.add_argument("--jsonl", type=Path, required=True, help="Input JSONL file.")
    run.add_argument("--out", type=Path, required=True, help="Output JSONL file.")

    submit = subparsers.add_parser("submit-track1", help="Run the official ACT II Track 1 file contract.")
    submit.add_argument("--input", type=Path, default=Path("/input/tasks.json"), help="Official input tasks JSON.")
    submit.add_argument("--output", type=Path, default=Path("/output/results.json"), help="Official output results JSON.")

    eval_parser = subparsers.add_parser("eval", help="Run JSONL tasks and optionally compare expected answers.")
    eval_parser.add_argument("--jsonl", type=Path, required=True, help="Input JSONL file.")
    eval_parser.add_argument("--expected", type=Path, help="Expected JSONL file with answers.")
    eval_parser.add_argument("--out", type=Path, help="Optional output JSONL file.")
    eval_parser.add_argument("--report", type=Path, help="Optional Markdown report path.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = RouterConfig.from_env()
        if args.command == "submit-track1":
            _validate_track1_runtime_environment(config)
        logger = JsonlRunLogger(config.log_path)
        runner = build_runner(config, logger)
        if args.command == "ask":
            return _handle_ask(args, runner)
        if args.command == "solve":
            return _handle_solve(args, runner)
        if args.command == "run":
            return _handle_run(args, runner)
        if args.command == "submit-track1":
            return _handle_submit_track1(args, runner)
        if args.command == "eval":
            return _handle_eval(args, runner)
    except Exception as exc:  # pragma: no cover - exercised through CLI behavior
        print(f"router error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"Unknown command: {args.command}")
    return 2


def _validate_track1_runtime_environment(config: RouterConfig) -> None:
    remote_modes = {"fireworks", "three_route", "hybrid"}
    uses_fireworks = config.mode.casefold() in remote_modes or (
        config.mode.casefold() == "competition" and not config.competition_dry_run
    )
    if not uses_fireworks:
        return
    missing = [
        name
        for name in ("FIREWORKS_API_KEY", "FIREWORKS_BASE_URL", "ALLOWED_MODELS")
        if not os.environ.get(name, "").strip()
    ]
    if missing:
        raise ValueError("Official Fireworks runtime requires harness variables: " + ", ".join(missing))
    if not config.allowed_models:
        raise ValueError("ALLOWED_MODELS did not contain any valid model IDs.")
    if config.fireworks_model not in config.allowed_models:
        raise ValueError("Selected Fireworks model is not authorized by ALLOWED_MODELS.")


def _handle_ask(args: argparse.Namespace, runner: TaskRunner) -> int:
    text = _read_ask_text(args)
    task = task_from_text(text, task_id=args.task_id)
    result = runner.run(task)
    if args.json:
        print(result.to_json())
    else:
        print(result.answer)
    return 0


def _handle_solve(args: argparse.Namespace, runner: TaskRunner) -> int:
    if not args.json:
        raise ValueError("solve currently requires --json so the evaluator contract stays explicit.")
    task = parse_json_task(sys.stdin.read())
    result = runner.run(task)
    print(result.to_json())
    return 0


def _handle_run(args: argparse.Namespace, runner: TaskRunner) -> int:
    tasks = load_jsonl_tasks(args.jsonl)
    results = [runner.run(task) for task in tasks]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        write_jsonl_results(results, handle)
    print(json.dumps({"tasks": len(results), "out": str(args.out)}, ensure_ascii=False), file=sys.stderr)
    return 0


def _handle_submit_track1(args: argparse.Namespace, runner: TaskRunner) -> int:
    adapter = get_adapter("lablab_track1")
    raw = args.input.read_text(encoding="utf-8")
    tasks = adapter.parse(raw)
    started_at = perf_counter()
    max_runtime_s = _float_env("TRACK1_MAX_RUNTIME_S", 570.0)
    reserve_s = _float_env("TRACK1_RUNTIME_RESERVE_S", 5.0)
    set_run_deadline = getattr(runner, "set_run_deadline", None)
    if callable(set_run_deadline):
        set_run_deadline(started_at + max(0.0, max_runtime_s - reserve_s))
    results = []
    for task in tasks:
        if _runtime_budget_exhausted(started_at, max_runtime_s, reserve_s):
            results.append(finalize_answer_result(task, _track1_timeout_result(task, started_at, max_runtime_s, reserve_s)))
            continue
        result = finalize_answer_result(task, runner.run(task))
        if result.route == "fireworks_error":
            raise RuntimeError(f"Fireworks failed for task_id={task.id}; refusing to publish a synthetic answer.")
        results.append(result)
    _validate_track1_alignment(tasks, results)
    _write_atomic_text(args.output, adapter.format(results))
    _write_optional_resource_report(started_at, tasks=len(tasks), results=len(results))
    print(json.dumps({"tasks": len(results), "out": str(args.output)}, ensure_ascii=False), file=sys.stderr)
    return 0


def _runtime_budget_exhausted(started_at: float, max_runtime_s: float, reserve_s: float) -> bool:
    return (perf_counter() - started_at) >= max(0.0, max_runtime_s - reserve_s)


def _write_atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_track1_alignment(tasks: list[TaskEnvelope], results: list[AnswerResult]) -> None:
    task_ids = [task.id for task in tasks]
    result_ids = [result.id for result in results]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("Track 1 input contains duplicate task_id values.")
    if result_ids != task_ids:
        raise ValueError("Track 1 results must preserve the exact input task_id order and cardinality.")


def _track1_timeout_result(
    task: TaskEnvelope,
    started_at: float,
    max_runtime_s: float,
    reserve_s: float,
) -> AnswerResult:
    return AnswerResult(
        id=task.id,
        answer="Unable to complete the task within the available time budget.",
        route="track1_time_budget_exhausted",
        metadata={
            "runner": "submit_track1",
            "reason": "track1_total_runtime_budget_exhausted",
            "elapsed_run_ms": round((perf_counter() - started_at) * 1000),
            "max_runtime_s": max_runtime_s,
            "reserve_s": reserve_s,
        },
    )


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _write_optional_resource_report(started_at: float, *, tasks: int, results: int) -> None:
    raw_path = os.getenv("ROUTER_RESOURCE_REPORT")
    if not raw_path or not raw_path.strip():
        return
    usage = resource.getrusage(resource.RUSAGE_SELF)
    max_rss = int(usage.ru_maxrss)
    # Linux reports KiB; macOS reports bytes. The official image is Linux.
    max_rss_kib = max_rss // 1024 if sys.platform == "darwin" else max_rss
    path = Path(raw_path.strip())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "router-resource-report-v1",
                "tasks": tasks,
                "results": results,
                "elapsed_ms": round((perf_counter() - started_at) * 1000),
                "max_rss_kib": max_rss_kib,
                "max_rss_mib": round(max_rss_kib / 1024, 3),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _handle_eval(args: argparse.Namespace, runner: TaskRunner) -> int:
    tasks = load_jsonl_tasks(args.jsonl)
    results = [runner.run(task) for task in tasks]
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as handle:
            write_jsonl_results(results, handle)

    summary = _build_eval_summary(tasks, results, args.expected)
    if args.report:
        _write_eval_report(args.report, summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def _read_ask_text(args: argparse.Namespace) -> str:
    if args.file and args.text:
        raise ValueError("Use either positional text or --file, not both.")
    if args.file:
        return args.file.read_text(encoding="utf-8")
    if args.text is not None:
        return args.text
    return sys.stdin.read()


def _build_eval_summary(
    tasks: list[TaskEnvelope],
    results: list[AnswerResult],
    expected_path: Path | None,
) -> dict[str, object]:
    route_counts = _count_routes(results)
    remote_tokens = _sum_remote_tokens(results)
    expected_by_id = _load_expected_answers(expected_path) if expected_path else {}
    summary: dict[str, object] = {
        "tasks": len(results),
        "routes": route_counts,
        "remote_tokens": remote_tokens,
        "escalation_rate": _rate(_count_escalations(results), len(results)),
        "replacement_rate": _rate(route_counts.get("fireworks_replaced", 0), len(results)),
        "parse_failures": sum(1 for result in results if result.metadata.get("fireworks_parse_failed")),
        "latency_ms": _latency_summary(results),
        "final_answer_chars": sum(len(result.answer) for result in results),
        "categories": _group_summary(tasks, results, expected_by_id, "category"),
        "difficulties": _group_summary(tasks, results, expected_by_id, "difficulty"),
        "expected_route": _expected_route_summary(tasks, results),
    }
    if expected_path is None:
        return summary

    comparable = [result for result in results if result.id in expected_by_id]
    exact_matches = sum(1 for result in comparable if result.answer.strip() == expected_by_id[result.id].strip())
    summary.update(
        {
            "comparable": len(comparable),
            "exact_matches": exact_matches,
            "exact_match_rate": exact_matches / len(comparable) if comparable else 0.0,
        }
    )
    return summary


def _count_routes(results: list[AnswerResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.route] = counts.get(result.route, 0) + 1
    return counts


def _sum_remote_tokens(results: list[AnswerResult]) -> dict[str, int]:
    return {
        "prompt": sum(result.remote_tokens.prompt for result in results),
        "completion": sum(result.remote_tokens.completion for result in results),
        "total": sum(result.remote_tokens.total for result in results),
    }


def _count_escalations(results: list[AnswerResult]) -> int:
    escalated_routes = {
        "m2b_candidate",
        "m2b_fireworks_approved",
        "m2b_fireworks_error_approved",
        "fireworks_replaced",
        "m2b_error_return_m1",
    }
    return sum(1 for result in results if result.route in escalated_routes)


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def _latency_summary(results: list[AnswerResult]) -> dict[str, int]:
    keys = ["latency_m1_ms", "latency_m2a_ms", "latency_m2b_ms", "latency_fireworks_ms"]
    return {
        key: sum(int(result.metadata.get(key) or 0) for result in results)
        for key in keys
    }


def _load_expected_answers(path: Path) -> dict[str, str]:
    expected: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected JSONL line {line_number} must be an object.")
            task_id = payload.get("id")
            answer = payload.get("answer", payload.get("expected", payload.get("input_text")))
            if task_id is not None and answer is not None:
                expected[str(task_id)] = str(answer)
    return expected


def _group_summary(
    tasks: list[TaskEnvelope],
    results: list[AnswerResult],
    expected_by_id: dict[str, str],
    metadata_key: str,
) -> dict[str, dict[str, object]]:
    grouped: dict[str, list[tuple[TaskEnvelope, AnswerResult]]] = {}
    for task, result in zip(tasks, results):
        group = str(task.metadata.get(metadata_key) or "unknown")
        grouped.setdefault(group, []).append((task, result))

    summary: dict[str, dict[str, object]] = {}
    for group, pairs in sorted(grouped.items()):
        group_results = [result for _task, result in pairs]
        comparable = [result for result in group_results if result.id in expected_by_id]
        exact_matches = sum(
            1
            for result in comparable
            if result.answer.strip() == expected_by_id[result.id].strip()
        )
        summary[group] = {
            "tasks": len(pairs),
            "routes": _count_routes(group_results),
            "remote_tokens": _sum_remote_tokens(group_results),
            "escalation_rate": _rate(_count_escalations(group_results), len(group_results)),
            "comparable": len(comparable),
            "exact_matches": exact_matches,
            "exact_match_rate": exact_matches / len(comparable) if comparable else 0.0,
        }
    return summary


def _expected_route_summary(tasks: list[TaskEnvelope], results: list[AnswerResult]) -> dict[str, object]:
    comparable = [
        (task, result)
        for task, result in zip(tasks, results)
        if task.metadata.get("expected_route")
    ]
    matches = sum(
        1
        for task, result in comparable
        if str(task.metadata["expected_route"]) == result.route
    )
    return {
        "comparable": len(comparable),
        "matches": matches,
        "match_rate": matches / len(comparable) if comparable else 0.0,
    }


def _write_eval_report(path: Path, summary: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Eval Report",
        "",
        f"- tasks: {summary.get('tasks')}",
        f"- exact_match_rate: {summary.get('exact_match_rate', 'n/a')}",
        f"- escalation_rate: {summary.get('escalation_rate')}",
        f"- replacement_rate: {summary.get('replacement_rate')}",
        f"- parse_failures: {summary.get('parse_failures')}",
        f"- remote_tokens: `{json.dumps(summary.get('remote_tokens'), sort_keys=True)}`",
        f"- routes: `{json.dumps(summary.get('routes'), sort_keys=True)}`",
        f"- latency_ms: `{json.dumps(summary.get('latency_ms'), sort_keys=True)}`",
        f"- expected_route: `{json.dumps(summary.get('expected_route'), sort_keys=True)}`",
        "",
    ]
    categories = summary.get("categories")
    if isinstance(categories, dict) and categories:
        lines.extend(["## Categories", ""])
        lines.append("| category | tasks | exact_match_rate | escalation_rate | routes |")
        lines.append("|---|---:|---:|---:|---|")
        for category, payload in categories.items():
            if not isinstance(payload, dict):
                continue
            lines.append(
                "| "
                f"{category} | "
                f"{payload.get('tasks')} | "
                f"{payload.get('exact_match_rate')} | "
                f"{payload.get('escalation_rate')} | "
                f"`{json.dumps(payload.get('routes'), sort_keys=True)}` |"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
