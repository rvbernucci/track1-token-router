from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.orchestration.matrix_regression_selector import (
    FEATURE_NAMES,
    fit_matrix_regression,
    load_microbench_rows,
    load_regression_tasks,
    save_weights,
    select_model_by_matrix_regression,
)
from router.orchestration.fireworks_model_router import rank_fireworks_models


DEFAULT_DATASET = Path("evals/fireworks-pareto/minimal-microbench.jsonl")
DEFAULT_REAL_RESULTS = [
    Path("reports/generated/fireworks-microbench-results.jsonl"),
    Path("reports/generated/fireworks-microbench-gpt-low-results.jsonl"),
]
DEFAULT_SEED_RESULTS = [
    Path("evals/fireworks-pareto/seed-microbench-results.jsonl"),
]
DEFAULT_WEIGHTS = Path("reports/generated/fireworks-matrix-regression-weights.json")
DEFAULT_REPORT = Path("reports/generated/fireworks-matrix-regression-report.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fit an offline matrix regression for Fireworks model selection.")
    parser.add_argument("--dataset", action="append", type=Path, help="Task JSONL dataset. Can be repeated.")
    parser.add_argument("--results", action="append", type=Path, help="Microbench JSONL result path. Can be repeated.")
    parser.add_argument("--allowed-models", help="Comma-separated model IDs. Rows for other models are ignored.")
    parser.add_argument(
        "--include-failed-calls",
        action="store_true",
        help="Include transport/access failures in training. By default only completed model calls are used.",
    )
    parser.add_argument("--weights-output", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--ridge-lambda", type=float, default=0.35)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result_paths = args.results or _default_result_paths()
    if not result_paths:
        raise FileNotFoundError("No microbench result files found. Run scripts/fireworks_microbench.py or keep the seed results fixture.")
    raw_rows = load_microbench_rows(result_paths)
    tasks = load_all_regression_tasks(tuple(args.dataset or [DEFAULT_DATASET]))
    models = rank_fireworks_models(_parse_models(args.allowed_models)) or sorted({str(row["model"]) for row in raw_rows})
    rows = filter_training_rows(raw_rows, tasks, models, include_failed_calls=args.include_failed_calls)
    weights = fit_matrix_regression(rows, tasks, allowed_models=models, ridge_lambda=args.ridge_lambda)
    save_weights(weights, args.weights_output)
    report = _render_report(rows, tasks, models, weights, result_paths)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    payload = {
        "raw_rows": len(raw_rows),
        "rows": len(rows),
        "datasets": [str(path) for path in tuple(args.dataset or [DEFAULT_DATASET])],
        "models": models,
        "weights_output": str(args.weights_output),
        "report": str(args.report),
        "top_coefficients": _top_coefficients(weights.coefficients, 8),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
    else:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


def _default_result_paths() -> list[Path]:
    real_results = [path for path in DEFAULT_REAL_RESULTS if path.exists()]
    if real_results:
        return real_results
    return [path for path in DEFAULT_SEED_RESULTS if path.exists()]


def load_all_regression_tasks(paths: tuple[Path, ...]) -> dict[str, Any]:
    tasks: dict[str, Any] = {}
    for path in paths:
        for task_id, task in load_regression_tasks(path).items():
            tasks[task_id] = task
    return tasks


def filter_training_rows(
    rows: list[dict[str, Any]],
    tasks: dict[str, Any],
    allowed_models: list[str],
    *,
    include_failed_calls: bool = False,
) -> list[dict[str, Any]]:
    allowed = set(allowed_models)
    filtered: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        task_id = str(row.get("id") or "")
        model = str(row.get("model") or "")
        if task_id not in tasks or model not in allowed:
            continue
        if not include_failed_calls and row.get("ok") is False:
            continue
        key = (task_id, model, str(row.get("request_options") or {}))
        if key in seen:
            continue
        seen.add(key)
        filtered.append(row)
    return filtered


def _parse_models(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [model.strip() for model in raw.split(",") if model.strip()]


def _render_report(
    rows: list[dict[str, Any]],
    tasks: dict[str, Any],
    models: list[str],
    weights: Any,
    result_paths: list[Path],
) -> str:
    lines = [
        "# Fireworks Matrix Regression Report",
        "",
        f"- training_rows: `{weights.training_rows}`",
        f"- ridge_lambda: `{weights.ridge_lambda}`",
        f"- target_mean: `{weights.target_mean:.4f}`",
        f"- result_paths: `{', '.join(str(path) for path in result_paths)}`",
        "",
        "## Learned Coefficients",
        "",
        "| Feature | Coefficient |",
        "| --- | ---: |",
    ]
    for name, coefficient in sorted(zip(FEATURE_NAMES, weights.coefficients), key=lambda pair: abs(pair[1]), reverse=True):
        lines.append(f"| `{name}` | {coefficient:.5f} |")
    lines.extend(["", "## Empirical Domain Matrix", ""])
    lines.extend(_domain_matrix_lines(weights))
    lines.extend(["", "## Selection Replay", ""])
    lines.extend(_selection_replay_lines(rows, tasks, models, weights))
    lines.extend(["", "## Interpretation", ""])
    lines.append("- Positive coefficients increase the learned utility for a model/task pair.")
    lines.append("- Negative coefficients reduce utility and usually indicate observed failures, overthinking, cost drag, or mode mismatch.")
    lines.append("- Domain/model empirical validity is smoothed before scoring, so one lucky or unlucky call cannot dominate Nash welfare.")
    lines.append("- The runtime combines ridge utility, Nash welfare, token utility and empirical risk; it does not hardcode domain winners.")
    lines.append("")
    return "\n".join(lines)


def _domain_matrix_lines(weights: Any) -> list[str]:
    stats = getattr(weights, "domain_model_stats", None) or {}
    if not stats:
        return ["- no empirical stats recorded"]
    lines = [
        "| Domain | Model | Calls | Valid | Smoothed Valid Rate | Avg Tokens | Avg Cost USD |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for domain, models in sorted(stats.items()):
        if domain == "__overall__":
            continue
        for model, row in sorted(models.items()):
            calls = float(row.get("calls") or 0.0)
            valid = float(row.get("valid") or 0.0)
            lines.append(
                f"| `{domain}` | `{model}` | {calls:.0f} | {valid:.0f} "
                f"| {float(row.get('valid_rate_smoothed') or 0.0):.3f} "
                f"| {float(row.get('avg_total_tokens') or 0.0):.0f} "
                f"| {float(row.get('avg_cost_usd') or 0.0):.8f} |"
            )
    return lines


def _selection_replay_lines(
    rows: list[dict[str, Any]],
    tasks: dict[str, Any],
    models: list[str],
    weights: Any,
) -> list[str]:
    observed = _observed_by_task_model(rows)
    lines = [
        "| Task | Domain | Selected | Observed | Observed Valid | Observed Cost USD | Score |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for task_id, task in sorted(tasks.items()):
        selection = select_model_by_matrix_regression(
            TaskEnvelope(id=task_id, input_text=task.prompt),
            models,
            weights,
        )
        selected = selection["model"]
        observed_row = observed.get((task_id, selected))
        observed_flag = observed_row is not None
        valid = int(bool(observed_row.get("valid"))) if observed_row else "-"
        cost = f"{float(observed_row.get('estimated_cost_usd') or 0.0):.8f}" if observed_row else "-"
        score = selection["ranked_candidates"][0]["hybrid_score"]
        lines.append(
            f"| `{task_id}` | `{selection['domain']}` | `{selected}` | {int(observed_flag)} | {valid} | {cost} | {score:.5f} |"
        )
    return lines


def _observed_by_task_model(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row["id"]), str(row["model"]))
        current = best.get(key)
        if current is None or _row_rank(row) > _row_rank(current):
            best[key] = row
    return best


def _row_rank(row: dict[str, Any]) -> tuple[int, float, float]:
    return (
        1 if row.get("valid") else 0,
        -float(row.get("estimated_cost_usd") or 0.0),
        -float(row.get("latency_ms") or 0.0),
    )


def _top_coefficients(coefficients: list[float], limit: int) -> list[dict[str, Any]]:
    ranked = sorted(zip(FEATURE_NAMES, coefficients), key=lambda pair: abs(pair[1]), reverse=True)
    return [
        {"feature": feature, "coefficient": coefficient}
        for feature, coefficient in ranked[:limit]
    ]


if __name__ == "__main__":
    raise SystemExit(main())
