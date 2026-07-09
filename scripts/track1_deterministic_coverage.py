from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.core.mock_runner import MockCascadeRunner
from router.orchestration.competition import CompetitionRunner
from scripts.fireworks_microbench import _load_tasks, _validate


DEFAULT_DATASETS = (
    Path("evals/fireworks-pareto/track1-category-microbench.jsonl"),
    Path("evals/fireworks-pareto/championship-microbench.jsonl"),
    Path("evals/fireworks-pareto/hidden-variant-microbench.jsonl"),
)
DEFAULT_REPORT = Path("reports/generated/track1-deterministic-coverage.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check deterministic Track 1 solver coverage against local validators.")
    parser.add_argument("--dataset", action="append", type=Path, help="JSONL dataset to evaluate. Can be repeated.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--min-coverage", type=float, default=0.40)
    parser.add_argument("--json", action="store_true", help="Print the full JSON report.")
    parser.add_argument("--check", action="store_true", help="Fail if deterministic coverage or validity falls below threshold.")
    args = parser.parse_args()

    datasets = tuple(args.dataset or DEFAULT_DATASETS)
    report = build_report(datasets, min_coverage=args.min_coverage)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_markdown(report), encoding="utf-8")

    payload = report if args.json else {
        "ok": report["ok"],
        "datasets": len(report["datasets"]),
        "total_tasks": report["totals"]["tasks"],
        "deterministic_tasks": report["totals"]["deterministic_tasks"],
        "coverage_rate": report["totals"]["coverage_rate"],
        "invalid_deterministic_outputs": len(report["invalid_deterministic_outputs"]),
        "report": str(args.report),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if report["ok"] or not args.check else 1


def build_report(datasets: tuple[Path, ...], *, min_coverage: float = 0.40) -> dict[str, Any]:
    rows = [_evaluate_dataset(path) for path in datasets]
    invalid = [
        invalid_row
        for dataset in rows
        for invalid_row in dataset["invalid_deterministic_outputs"]
    ]
    low_coverage = [
        {
            "dataset": row["dataset"],
            "coverage_rate": row["coverage_rate"],
            "min_coverage": min_coverage,
        }
        for row in rows
        if row["coverage_rate"] < min_coverage
    ]
    total_tasks = sum(int(row["tasks"]) for row in rows)
    deterministic_tasks = sum(int(row["deterministic_tasks"]) for row in rows)
    valid_deterministic = sum(int(row["valid_deterministic_outputs"]) for row in rows)
    totals = {
        "tasks": total_tasks,
        "deterministic_tasks": deterministic_tasks,
        "valid_deterministic_outputs": valid_deterministic,
        "coverage_rate": _rate(deterministic_tasks, total_tasks),
        "valid_deterministic_rate": _rate(valid_deterministic, deterministic_tasks),
    }
    return {
        "ok": not invalid and not low_coverage,
        "min_coverage": min_coverage,
        "datasets": rows,
        "totals": totals,
        "invalid_deterministic_outputs": invalid,
        "low_coverage": low_coverage,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Track 1 Deterministic Coverage",
        "",
        f"- ok: `{report['ok']}`",
        f"- min_coverage: `{report['min_coverage']}`",
        f"- total_tasks: `{report['totals']['tasks']}`",
        f"- deterministic_tasks: `{report['totals']['deterministic_tasks']}`",
        f"- coverage_rate: `{report['totals']['coverage_rate']:.3f}`",
        f"- valid_deterministic_rate: `{report['totals']['valid_deterministic_rate']:.3f}`",
        "",
        "## Datasets",
        "",
        "| dataset | tasks | deterministic | coverage | valid deterministic | invalid | routes |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["datasets"]:
        lines.append(
            "| "
            f"{row['dataset']} | "
            f"{row['tasks']} | "
            f"{row['deterministic_tasks']} | "
            f"{row['coverage_rate']:.3f} | "
            f"{row['valid_deterministic_outputs']} | "
            f"{len(row['invalid_deterministic_outputs'])} | "
            f"`{json.dumps(row['routes'], sort_keys=True)}` |"
        )
    lines.extend(["", "## Invalid Deterministic Outputs", ""])
    if report["invalid_deterministic_outputs"]:
        for row in report["invalid_deterministic_outputs"]:
            lines.append(
                f"- `{row['dataset']}` `{row['id']}` route `{row['route']}` failed: {row['reason']}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Low Coverage", ""])
    if report["low_coverage"]:
        for row in report["low_coverage"]:
            lines.append(
                f"- `{row['dataset']}` coverage `{row['coverage_rate']:.3f}` below `{row['min_coverage']:.3f}`"
            )
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def _evaluate_dataset(path: Path) -> dict[str, Any]:
    tasks = _load_tasks(path)
    runner = CompetitionRunner(MockCascadeRunner(), dry_run=True)
    routes: Counter[str] = Counter()
    deterministic = 0
    valid_deterministic = 0
    invalid: list[dict[str, str]] = []
    by_domain: dict[str, Counter[str]] = {}

    for task in tasks:
        envelope = TaskEnvelope(
            id=task.id,
            input_text=task.prompt,
            metadata={"domain": task.domain, "tier": task.tier},
        )
        result = runner.run(envelope)
        routes[result.route] += 1
        by_domain.setdefault(task.domain, Counter())[result.route] += 1
        if not _is_deterministic_route(result.route):
            continue
        deterministic += 1
        validation = _validate(task.validator, result.answer)
        if validation["valid"]:
            valid_deterministic += 1
        else:
            invalid.append(
                {
                    "dataset": str(path),
                    "id": task.id,
                    "route": result.route,
                    "reason": str(validation["reason"]),
                    "answer_preview": _preview(result.answer),
                }
            )

    return {
        "dataset": str(path),
        "tasks": len(tasks),
        "deterministic_tasks": deterministic,
        "valid_deterministic_outputs": valid_deterministic,
        "coverage_rate": _rate(deterministic, len(tasks)),
        "valid_deterministic_rate": _rate(valid_deterministic, deterministic),
        "invalid_deterministic_outputs": invalid,
        "routes": dict(sorted(routes.items())),
        "routes_by_domain": {domain: dict(sorted(counter.items())) for domain, counter in sorted(by_domain.items())},
    }


def _is_deterministic_route(route: str) -> bool:
    return route.startswith("solver_") or route.startswith("guardrail_")


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _preview(value: str) -> str:
    collapsed = " ".join(value.strip().split())
    return collapsed[:160]


if __name__ == "__main__":
    raise SystemExit(main())
