from __future__ import annotations

import argparse
import ast
import builtins
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

from router.core.fireworks import FireworksClient
from router.core.model_client import ModelClientError, ModelResponse
from router.orchestration.fireworks_model_router import _profile_for_model, normalize_fireworks_model_id, select_reasoning_effort


DEFAULT_BASE_URL = "https://api.fireworks.ai/inference/v1"
DEFAULT_DATASET = Path("evals/fireworks-pareto/minimal-microbench.jsonl")
DEFAULT_OUTPUT_JSONL = Path("reports/generated/fireworks-microbench-results.jsonl")
DEFAULT_REPORT = Path("reports/generated/fireworks-microbench-report.md")
DEFAULT_ENV_FILES = (Path(".env.fireworks"), Path(".env.fireworks.local"))
DEFAULT_MODELS = [
    "accounts/fireworks/models/gpt-oss-20b",
    "accounts/fireworks/models/gpt-oss-120b",
    "accounts/fireworks/models/deepseek-v4-flash",
    "accounts/fireworks/models/minimax-m3",
    "accounts/fireworks/models/qwen3p7-plus",
    "accounts/fireworks/models/kimi-k2p7-code",
]
SYSTEM_PROMPT = (
    "You are running a tiny routing benchmark. Follow the user instruction exactly. "
    "Return only the requested final answer. Do not explain."
)


@dataclass(frozen=True)
class BenchTask:
    id: str
    domain: str
    tier: str
    prompt: str
    validator: dict[str, Any]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a tiny Fireworks model microbenchmark.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--models", help="Comma-separated model IDs. Defaults to a compact Pareto set.")
    parser.add_argument("--base-url")
    parser.add_argument("--env-file", action="append", type=Path, help="Load KEY=VALUE pairs before running.")
    parser.add_argument("--output-jsonl", type=Path, default=DEFAULT_OUTPUT_JSONL)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--timeout-s", type=float, default=45.0)
    parser.add_argument("--max-retries", type=int, default=0)
    parser.add_argument("--max-calls", type=int, default=36)
    parser.add_argument("--budget-usd", type=float, default=0.25)
    parser.add_argument("--progress-every", type=int, default=0, help="Print progress to stderr every N completed calls.")
    parser.add_argument(
        "--reasoning-effort-override",
        choices=["auto", "off", "none", "low", "medium", "high"],
        default="auto",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print compact JSON summary.")
    args = parser.parse_args()

    _load_env_files(tuple(args.env_file or DEFAULT_ENV_FILES))
    api_key = os.getenv("FIREWORKS_API_KEY")
    tasks = _load_tasks(args.dataset)
    models = _parse_models(args.models) or DEFAULT_MODELS
    plan = _build_plan(tasks, models, args.max_tokens)
    scheduled_plan = plan[: args.max_calls]

    estimated_plan_cost = sum(item["estimated_cost_usd"] for item in scheduled_plan)
    if estimated_plan_cost > args.budget_usd:
        print(
            f"Estimated plan cost ${estimated_plan_cost:.6f} exceeds --budget-usd=${args.budget_usd:.6f}.",
            file=sys.stderr,
        )
        return 2

    if args.dry_run:
        payload = {
            "dry_run": True,
            "dataset": str(args.dataset),
            "models": models,
            "tasks": [task.id for task in tasks],
            "planned_calls": len(plan),
            "scheduled_calls": len(scheduled_plan),
            "estimated_plan_cost_usd": round(estimated_plan_cost, 8),
            "max_tokens": args.max_tokens,
            "budget_usd": args.budget_usd,
            "reasoning_effort_override": args.reasoning_effort_override,
        }
        _print_summary(payload, args.json)
        return 0

    if not api_key:
        print("FIREWORKS_API_KEY is not set. This script never prints FIREWORKS_API_KEY.", file=sys.stderr)
        return 2

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    spent_estimate = 0.0
    with args.output_jsonl.open("w", encoding="utf-8") as handle:
        for task in tasks:
            for model in models:
                if len(results) >= args.max_calls:
                    break
                if spent_estimate >= args.budget_usd:
                    break
                result = _run_case(
                    base_url=args.base_url or os.getenv("FIREWORKS_BASE_URL") or DEFAULT_BASE_URL,
                    api_key=api_key,
                    model=model,
                    task=task,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    timeout_s=args.timeout_s,
                    max_retries=args.max_retries,
                    reasoning_effort_override=args.reasoning_effort_override,
                )
                spent_estimate += float(result.get("estimated_cost_usd") or 0.0)
                results.append(result)
                handle.write(json.dumps(result, ensure_ascii=True, separators=(",", ":")) + "\n")
                handle.flush()
                if args.progress_every > 0 and len(results) % args.progress_every == 0:
                    print(
                        json.dumps(
                            {
                                "completed": len(results),
                                "valid": sum(1 for item in results if item.get("valid")),
                                "estimated_cost_usd": round(spent_estimate, 8),
                                "last_model": model,
                                "last_task": task.id,
                            },
                            ensure_ascii=True,
                            separators=(",", ":"),
                        ),
                        file=sys.stderr,
                    )
            if len(results) >= args.max_calls or spent_estimate >= args.budget_usd:
                break

    report = _render_report(results, args.dataset, models, args.max_tokens, args.budget_usd)
    args.report.write_text(report, encoding="utf-8")
    summary = _summarize(results)
    summary.update(
        {
            "output_jsonl": str(args.output_jsonl),
            "report": str(args.report),
            "estimated_cost_usd": round(spent_estimate, 8),
        }
    )
    _print_summary(summary, args.json)
    return 0


def _run_case(
    *,
    base_url: str,
    api_key: str,
    model: str,
    task: BenchTask,
    temperature: float,
    max_tokens: int,
    timeout_s: float,
    max_retries: int,
    reasoning_effort_override: str,
) -> dict[str, Any]:
    client = FireworksClient(
        base_url=base_url,
        model=model,
        api_key=api_key,
        timeout_s=timeout_s,
        max_retries=max_retries,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task.prompt},
    ]
    request_options = _request_options(model, task.tier, reasoning_effort_override)
    started_at = perf_counter()
    fallback_reason: str | None = None
    try:
        try:
            response = client.complete(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=request_options,
            )
        except ModelClientError as exc:
            if not _is_request_option_error(str(exc)):
                raise
            fallback_reason = str(exc)
            response = client.complete(messages, temperature=temperature, max_tokens=max_tokens)
    except ModelClientError as exc:
        latency_ms = _elapsed_ms(started_at)
        return {
            "id": task.id,
            "domain": task.domain,
            "tier": task.tier,
            "model": model,
            "ok": False,
            "valid": False,
            "latency_ms": latency_ms,
            "usage": {"prompt": 0, "completion": 0, "total": 0},
            "estimated_cost_usd": 0.0,
            "answer_preview": "",
            "error": _truncate(str(exc), 500),
            "request_options": _safe_options(request_options),
            "request_options_fallback": fallback_reason is not None,
        }
    latency_ms = _elapsed_ms(started_at)
    validation = _validate(task.validator, response.text)
    return {
        "id": task.id,
        "domain": task.domain,
        "tier": task.tier,
        "model": model,
        "ok": True,
        "valid": validation["valid"],
        "validator": task.validator.get("type"),
        "validation_reason": validation["reason"],
        "latency_ms": latency_ms,
        "usage": response.usage.to_dict(),
        "estimated_cost_usd": _actual_cost(model, response),
        "answer_preview": _truncate(_strip_code_fence(response.text).strip(), 220),
        "error": "",
        "request_options": _safe_options(request_options),
        "request_options_fallback": fallback_reason is not None,
    }


def _request_options(model: str, tier: str, reasoning_effort_override: str) -> dict[str, Any]:
    options: dict[str, Any] = {"user": "track1-microbench-v1"}
    if reasoning_effort_override == "off":
        reasoning_effort = None
    elif reasoning_effort_override == "auto":
        reasoning_effort = select_reasoning_effort(model, tier)
    else:
        reasoning_effort = reasoning_effort_override
    if reasoning_effort:
        options["reasoning_effort"] = reasoning_effort
    return options


def _safe_options(options: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in options.items() if key != "api_key"}


def _actual_cost(model: str, response: ModelResponse) -> float:
    profile = _profile_for_model(model)
    return (
        (response.usage.prompt * profile.input_price_per_mtok)
        + (response.usage.completion * profile.output_price_per_mtok)
    ) / 1_000_000


def _build_plan(tasks: list[BenchTask], models: list[str], max_tokens: int) -> list[dict[str, Any]]:
    plan = []
    for task in tasks:
        for model in models:
            prompt_tokens = _estimate_tokens(SYSTEM_PROMPT) + _estimate_tokens(task.prompt)
            profile = _profile_for_model(model)
            estimated_cost = (
                (prompt_tokens * profile.input_price_per_mtok)
                + (max_tokens * profile.output_price_per_mtok)
            ) / 1_000_000
            plan.append(
                {
                    "id": task.id,
                    "model": model,
                    "domain": task.domain,
                    "estimated_cost_usd": estimated_cost,
                }
            )
    return plan


def _load_tasks(path: Path) -> list[BenchTask]:
    tasks = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        tasks.append(
            BenchTask(
                id=str(payload["id"]),
                domain=str(payload["domain"]),
                tier=str(payload["tier"]),
                prompt=str(payload["prompt"]),
                validator=dict(payload["validator"]),
            )
        )
    if not tasks:
        raise ValueError(f"No tasks loaded from {path}")
    return tasks


def _validate(validator: dict[str, Any], answer: str) -> dict[str, Any]:
    kind = validator.get("type")
    clean = _strip_code_fence(answer).strip()
    if kind == "exact":
        expected = str(validator.get("expected", ""))
        return _validation(clean == expected, f"expected exact {expected!r}")
    if kind == "exact_lower":
        expected = str(validator.get("expected", "")).lower()
        return _validation(clean.lower() == expected, f"expected lowercase {expected!r}")
    if kind == "number_exact":
        expected = float(validator.get("expected"))
        match = re.search(r"-?\d+(?:\.\d+)?", clean)
        actual = float(match.group(0)) if match else None
        return _validation(actual is not None and abs(actual - expected) < 0.000001, f"expected number {expected:g}")
    if kind == "json_contains":
        try:
            payload = json.loads(clean)
        except json.JSONDecodeError:
            return _validation(False, "answer is not JSON")
        expected = validator.get("expected")
        if not isinstance(payload, dict) or not isinstance(expected, dict):
            return _validation(False, "expected and answer must be JSON objects")
        return _validation(all(payload.get(key) == value for key, value in expected.items()), "expected JSON key/value pairs")
    if kind == "contains_all_lower":
        expected_terms = [str(item).lower() for item in validator.get("terms", [])]
        lowered = clean.lower()
        missing = [term for term in expected_terms if term not in lowered]
        if missing:
            return _validation(False, f"missing terms: {missing}")
        max_words = validator.get("max_words")
        if max_words is not None and len(re.findall(r"\b\w+\b", clean)) > int(max_words):
            return _validation(False, f"expected at most {int(max_words)} words")
        return _validation(True, "all required terms present")
    if kind == "python_function_static":
        return _validate_python_function(clean, str(validator.get("function_name", "")))
    if kind == "python_function_cases":
        return _validate_python_function_cases(
            clean,
            str(validator.get("function_name", "")),
            list(validator.get("cases") or []),
        )
    return _validation(False, f"unknown validator {kind!r}")


def _validate_python_function(code: str, function_name: str) -> dict[str, Any]:
    try:
        module = ast.parse(code)
    except SyntaxError as exc:
        return _validation(False, f"syntax error: {exc.msg}")
    has_function = any(isinstance(node, ast.FunctionDef) and node.name == function_name for node in module.body)
    return _validation(has_function, f"expected function {function_name}")


def _validate_python_function_cases(code: str, function_name: str, cases: list[Any]) -> dict[str, Any]:
    try:
        module = ast.parse(code)
    except SyntaxError as exc:
        return _validation(False, f"syntax error: {exc.msg}")
    has_function = any(isinstance(node, ast.FunctionDef) and node.name == function_name for node in module.body)
    if not has_function:
        return _validation(False, f"expected function {function_name}")
    safety_error = _python_safety_error(module)
    if safety_error:
        return _validation(False, safety_error)
    namespace: dict[str, Any] = {"__builtins__": _safe_builtins()}
    try:
        exec(compile(module, "<fireworks-microbench>", "exec"), namespace, namespace)
        target = namespace.get(function_name)
        if not callable(target):
            return _validation(False, f"{function_name} is not callable")
        for index, case in enumerate(cases, start=1):
            if not isinstance(case, dict):
                return _validation(False, f"case {index} must be an object")
            args = case.get("args", [])
            kwargs = case.get("kwargs", {})
            expected = case.get("expected")
            if not isinstance(args, list) or not isinstance(kwargs, dict):
                return _validation(False, f"case {index} args/kwargs shape is invalid")
            actual = target(*args, **kwargs)
            if actual != expected:
                return _validation(False, f"case {index} expected {expected!r}, got {actual!r}")
    except Exception as exc:  # pragma: no cover - exercised by live model outputs
        return _validation(False, f"runtime error: {type(exc).__name__}: {_truncate(str(exc), 120)}")
    return _validation(True, f"{len(cases)} behavior cases passed")


def _python_safety_error(module: ast.AST) -> str:
    blocked_nodes = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.ClassDef)
    blocked_names = {"__import__", "eval", "exec", "compile", "open", "input", "breakpoint"}
    for node in ast.walk(module):
        if isinstance(node, blocked_nodes):
            return f"blocked Python construct: {type(node).__name__}"
        if isinstance(node, ast.Name) and node.id in blocked_names:
            return f"blocked Python name: {node.id}"
    return ""


def _safe_builtins() -> dict[str, Any]:
    allowed = [
        "abs",
        "all",
        "any",
        "bool",
        "dict",
        "enumerate",
        "filter",
        "float",
        "int",
        "len",
        "list",
        "map",
        "max",
        "min",
        "range",
        "reversed",
        "round",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
    ]
    return {name: getattr(builtins, name) for name in allowed}


def _validation(valid: bool, reason: str) -> dict[str, Any]:
    return {"valid": bool(valid), "reason": reason}


def _render_report(
    results: list[dict[str, Any]],
    dataset: Path,
    models: list[str],
    max_tokens: int,
    budget_usd: float,
) -> str:
    summary = _summarize(results)
    lines = [
        "# Fireworks Microbench Report",
        "",
        f"- dataset: `{dataset}`",
        f"- models: `{len(models)}`",
        f"- calls: `{summary['calls']}`",
        f"- max_tokens: `{max_tokens}`",
        f"- budget_usd: `{budget_usd}`",
        f"- estimated_cost_usd: `{summary['estimated_cost_usd']:.8f}`",
        "",
        "## Model Summary",
        "",
        "| Model | Calls | Valid | Valid Rate | Tokens | Cost USD | Avg Latency ms | Errors |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for model, row in sorted(summary["by_model"].items()):
        lines.append(
            f"| `{model}` | {row['calls']} | {row['valid']} | {row['valid_rate']:.2f} "
            f"| {row['tokens']} | {row['cost']:.8f} | {row['latency_ms_avg']:.0f} | {row['errors']} |"
        )
    lines.extend(["", "## Domain Winners", ""])
    lines.extend(_domain_winner_lines(results))
    lines.extend(["", "## Failed Cases", ""])
    failed = [item for item in results if not item.get("valid")]
    if not failed:
        lines.append("- none")
    for item in failed:
        lines.append(
            f"- `{item['id']}` / `{item['domain']}` / `{item['model']}`: "
            f"{item.get('validation_reason') or item.get('error')}"
        )
    lines.append("")
    return "\n".join(lines)


def _domain_winner_lines(results: list[dict[str, Any]]) -> list[str]:
    by_domain: dict[str, dict[str, dict[str, float]]] = {}
    for item in results:
        domain = str(item["domain"])
        model = str(item["model"])
        row = by_domain.setdefault(domain, {}).setdefault(model, {"calls": 0, "valid": 0, "cost": 0.0, "latency": 0.0})
        row["calls"] += 1
        row["valid"] += 1 if item.get("valid") else 0
        row["cost"] += float(item.get("estimated_cost_usd") or 0.0)
        row["latency"] += float(item.get("latency_ms") or 0.0)
    lines = ["| Domain | Winner | Valid Rate | Cost USD | Avg Latency ms |", "| --- | --- | ---: | ---: | ---: |"]
    for domain, models in sorted(by_domain.items()):
        ranked = sorted(
            models.items(),
            key=lambda pair: (
                -(pair[1]["valid"] / max(pair[1]["calls"], 1)),
                pair[1]["cost"],
                pair[1]["latency"] / max(pair[1]["calls"], 1),
                pair[0],
            ),
        )
        model, row = ranked[0]
        lines.append(
            f"| `{domain}` | `{model}` | {row['valid'] / max(row['calls'], 1):.2f} "
            f"| {row['cost']:.8f} | {row['latency'] / max(row['calls'], 1):.0f} |"
        )
    return lines


def _summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_model: dict[str, dict[str, Any]] = {}
    for item in results:
        model = str(item["model"])
        row = by_model.setdefault(
            model,
            {"calls": 0, "valid": 0, "tokens": 0, "cost": 0.0, "latency_ms": 0.0, "errors": 0},
        )
        row["calls"] += 1
        row["valid"] += 1 if item.get("valid") else 0
        row["tokens"] += int(item.get("usage", {}).get("total") or 0)
        row["cost"] += float(item.get("estimated_cost_usd") or 0.0)
        row["latency_ms"] += float(item.get("latency_ms") or 0.0)
        row["errors"] += 0 if item.get("ok") else 1
    for row in by_model.values():
        calls = max(row["calls"], 1)
        row["valid_rate"] = row["valid"] / calls
        row["latency_ms_avg"] = row["latency_ms"] / calls
    return {
        "calls": len(results),
        "valid": sum(1 for item in results if item.get("valid")),
        "estimated_cost_usd": sum(float(item.get("estimated_cost_usd") or 0.0) for item in results),
        "by_model": by_model,
    }


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[A-Za-z0-9_-]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 4) + 1)


def _elapsed_ms(started_at: float) -> int:
    return round((perf_counter() - started_at) * 1000)


def _is_request_option_error(message: str) -> bool:
    lowered = message.lower()
    return "reasoning_effort" in lowered or "service_tier" in lowered or "extra inputs are not permitted" in lowered


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[:limit] + "...[truncated]"


def _print_summary(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
    else:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))


def _load_env_files(paths: tuple[Path, ...]) -> None:
    loaded_from_file: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            key, value = _parse_env_line(line)
            if not key:
                continue
            if key in os.environ and key not in loaded_from_file:
                continue
            os.environ[key] = value
            loaded_from_file.add(key)


def _parse_env_line(line: str) -> tuple[str | None, str]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None, ""
    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None, ""
    return key, _strip_quotes(value.strip())


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_models(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [normalize_fireworks_model_id(item) for item in raw.split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
