from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from router.adapters.io import load_jsonl_tasks, parse_json_task, task_from_text, write_jsonl_results
from router.core.config import RouterConfig
from router.core.contracts import AnswerResult, TaskEnvelope
from router.core.logging import JsonlRunLogger
from router.core.runner import TaskRunner
from router.core.runner_factory import build_runner


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
        logger = JsonlRunLogger(config.log_path)
        runner = build_runner(config, logger)
        if args.command == "ask":
            return _handle_ask(args, runner)
        if args.command == "solve":
            return _handle_solve(args, runner)
        if args.command == "run":
            return _handle_run(args, runner)
        if args.command == "eval":
            return _handle_eval(args, runner)
    except Exception as exc:  # pragma: no cover - exercised through CLI behavior
        print(f"router error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"Unknown command: {args.command}")
    return 2


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


def _handle_eval(args: argparse.Namespace, runner: TaskRunner) -> int:
    tasks = load_jsonl_tasks(args.jsonl)
    results = [runner.run(task) for task in tasks]
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as handle:
            write_jsonl_results(results, handle)

    summary = _build_eval_summary(results, args.expected)
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


def _build_eval_summary(results: list[AnswerResult], expected_path: Path | None) -> dict[str, object]:
    route_counts = _count_routes(results)
    remote_tokens = _sum_remote_tokens(results)
    summary: dict[str, object] = {
        "tasks": len(results),
        "routes": route_counts,
        "remote_tokens": remote_tokens,
        "escalation_rate": _rate(_count_escalations(results), len(results)),
        "replacement_rate": _rate(route_counts.get("fireworks_replaced", 0), len(results)),
        "parse_failures": sum(1 for result in results if result.metadata.get("fireworks_parse_failed")),
        "latency_ms": _latency_summary(results),
        "final_answer_chars": sum(len(result.answer) for result in results),
    }
    if expected_path is None:
        return summary

    expected_by_id = _load_expected_answers(expected_path)
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
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
