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


DEFAULT_DATASET = Path("evals/fireworks-pareto/minimal-microbench.jsonl")
DEFAULT_RESULTS = [
    Path("reports/generated/fireworks-microbench-results.jsonl"),
    Path("reports/generated/fireworks-microbench-gpt-low-results.jsonl"),
]
DEFAULT_WEIGHTS = Path("reports/generated/fireworks-matrix-regression-weights.json")
DEFAULT_REPORT = Path("reports/generated/fireworks-matrix-regression-report.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fit an offline matrix regression for Fireworks model selection.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--results", action="append", type=Path, help="Microbench JSONL result path. Can be repeated.")
    parser.add_argument("--weights-output", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--ridge-lambda", type=float, default=0.35)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result_paths = args.results or DEFAULT_RESULTS
    rows = load_microbench_rows(result_paths)
    tasks = load_regression_tasks(args.dataset)
    models = sorted({str(row["model"]) for row in rows})
    weights = fit_matrix_regression(rows, tasks, allowed_models=models, ridge_lambda=args.ridge_lambda)
    save_weights(weights, args.weights_output)
    report = _render_report(rows, tasks, models, weights, result_paths)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    payload = {
        "rows": len(rows),
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
    lines.extend(["", "## Selection Replay", ""])
    lines.extend(_selection_replay_lines(rows, tasks, models, weights))
    lines.extend(["", "## Interpretation", ""])
    lines.append("- Positive coefficients increase the learned utility for a model/task pair.")
    lines.append("- Negative coefficients reduce utility and usually indicate observed failures, overthinking, cost drag, or mode mismatch.")
    lines.append("- This is an experimental calibration layer; it should not replace the Nash router until the dataset is larger.")
    lines.append("")
    return "\n".join(lines)


def _selection_replay_lines(
    rows: list[dict[str, Any]],
    tasks: dict[str, Any],
    models: list[str],
    weights: Any,
) -> list[str]:
    observed = _observed_by_task_model(rows)
    lines = [
        "| Task | Domain | Selected | Observed Valid | Observed Cost USD | Score |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for task_id, task in sorted(tasks.items()):
        selection = select_model_by_matrix_regression(
            TaskEnvelope(id=task_id, input_text=task.prompt),
            models,
            weights,
        )
        selected = selection["model"]
        observed_row = observed.get((task_id, selected))
        valid = bool(observed_row.get("valid")) if observed_row else False
        cost = float(observed_row.get("estimated_cost_usd") or 0.0) if observed_row else 0.0
        score = selection["ranked_candidates"][0]["hybrid_score"]
        lines.append(
            f"| `{task_id}` | `{selection['domain']}` | `{selected}` | {int(valid)} | {cost:.8f} | {score:.5f} |"
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
