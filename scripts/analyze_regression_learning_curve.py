#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.fit_engine_outcome_models import (
    _binary_metrics,
    _feature_names,
    _fit_binary_variant,
    _predict_binary_variant,
)


VARIANTS = ("constant", "logistic_linear", "logistic_nonlinear")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Measure lineage-safe regression learning curves without reading locked-test labels."
    )
    root.add_argument("--matrix", type=Path, required=True)
    root.add_argument("--engine", default="gemma4-e2b")
    root.add_argument("--sizes", default="100,250,500,1000")
    root.add_argument("--repeats", type=int, default=5)
    root.add_argument("--l2", type=float, default=0.75)
    root.add_argument("--plateau-brier", type=float, default=0.005)
    root.add_argument("--output", type=Path, required=True)
    root.add_argument("--report", type=Path, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    result = analyze_learning_curve(
        matrix_path=args.matrix,
        engine=args.engine,
        requested_sizes=_parse_sizes(args.sizes),
        repeats=args.repeats,
        l2=args.l2,
        plateau_brier=args.plateau_brier,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps(result["decision"], sort_keys=True))
    return 0


def analyze_learning_curve(
    *,
    matrix_path: Path,
    engine: str,
    requested_sizes: Sequence[int],
    repeats: int,
    l2: float,
    plateau_brier: float,
) -> dict[str, Any]:
    if repeats < 2 or l2 < 0 or plateau_brier < 0:
        raise ValueError("repeats must be >= 2, l2 non-negative and plateau threshold non-negative.")
    rows = [
        row
        for row in _jsonl(matrix_path)
        if str(row.get("model_id") or row.get("engine")) == engine
        and row.get("status") == "answered"
        and isinstance(row.get("correct"), bool)
    ]
    train = [row for row in rows if row.get("regression_split") == "train"]
    validation = [row for row in rows if row.get("regression_split") == "validation"]
    if not train or not validation:
        raise ValueError("Learning curve requires labeled train and validation rows.")
    if any(row.get("regression_split") not in {"train", "validation", "test"} for row in rows):
        raise ValueError("Every labeled row must have a fixed regression split.")
    feature_names = _feature_names([*train, *validation])
    sizes = sorted({size for size in requested_sizes if 2 <= size < len(train)} | {len(train)})
    points: list[dict[str, Any]] = []
    for size in sizes:
        runs: list[dict[str, Any]] = []
        repeat_count = 1 if size == len(train) else repeats
        for seed in range(repeat_count):
            sample = _nested_sample(train, size=size, seed=seed)
            variant_metrics: dict[str, Any] = {}
            for variant in VARIANTS:
                coefficients, _ = _fit_binary_variant(
                    sample,
                    feature_names,
                    variant=variant,
                    l2=l2,
                )
                pairs = [
                    (
                        float(bool(row["correct"])),
                        _predict_binary_variant(row, feature_names, variant, coefficients),
                    )
                    for row in validation
                ]
                variant_metrics[variant] = _binary_metrics(pairs)
            runs.append(
                {
                    "seed": seed,
                    "train_rows": len(sample),
                    "intent_counts": _intent_counts(sample),
                    "positive_rate": sum(bool(row["correct"]) for row in sample) / len(sample),
                    "metrics": variant_metrics,
                }
            )
        points.append(_summarize_point(size, runs))
    best_variant = min(
        VARIANTS,
        key=lambda variant: points[-1]["variants"][variant]["brier_mean"],
    )
    previous = points[-2] if len(points) > 1 else points[-1]
    improvement = (
        previous["variants"][best_variant]["brier_mean"]
        - points[-1]["variants"][best_variant]["brier_mean"]
    )
    plateau = len(points) > 1 and improvement <= plateau_brier
    return {
        "schema_version": "regression-learning-curve-v1",
        "matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
        "engine": engine,
        "locked_test_policy": "test rows and labels are never used by this analysis",
        "config": {
            "requested_sizes": list(requested_sizes),
            "effective_sizes": sizes,
            "repeats": repeats,
            "l2": l2,
            "plateau_brier": plateau_brier,
        },
        "data": {
            "train_rows": len(train),
            "validation_rows": len(validation),
            "test_rows_present_but_unread": sum(row.get("regression_split") == "test" for row in rows),
            "train_intent_counts": _intent_counts(train),
            "validation_intent_counts": _intent_counts(validation),
        },
        "points": points,
        "decision": {
            "best_full_train_variant": best_variant,
            "last_step_brier_improvement": improvement,
            "plateau_observed": plateau,
            "recommendation": (
                "Generate targeted uncertainty and failure-region examples before expanding broadly."
                if plateau
                else "More lineage-diverse training data may still improve calibration."
            ),
        },
    }


def _nested_sample(rows: Sequence[Mapping[str, Any]], *, size: int, seed: int) -> list[Mapping[str, Any]]:
    if not 1 <= size <= len(rows):
        raise ValueError("Sample size is outside the available training rows.")
    return sorted(rows, key=lambda row: _sample_key(row, seed))[:size]


def _sample_key(row: Mapping[str, Any], seed: int) -> str:
    identity = str(row.get("mutation_lineage") or row["task_id"])
    return hashlib.sha256(f"{seed}:{identity}".encode("utf-8")).hexdigest()


def _summarize_point(size: int, runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    variants: dict[str, Any] = {}
    for variant in VARIANTS:
        values = [run["metrics"][variant] for run in runs]
        variants[variant] = {
            "brier_mean": statistics.fmean(value["brier"] for value in values),
            "brier_stdev": statistics.stdev(value["brier"] for value in values) if len(values) > 1 else 0.0,
            "log_loss_mean": statistics.fmean(value["log_loss"] for value in values),
            "accuracy_mean": statistics.fmean(value["accuracy"] for value in values),
        }
    return {
        "train_rows": size,
        "repeats": len(runs),
        "positive_rate_mean": statistics.fmean(run["positive_rate"] for run in runs),
        "variants": variants,
    }


def _intent_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        intent = str(row["assessment"]["intent"])
        result[intent] = result.get(intent, 0) + 1
    return dict(sorted(result.items()))


def _parse_sizes(value: str) -> list[int]:
    try:
        sizes = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise ValueError("sizes must be comma-separated integers") from exc
    if not sizes or any(size < 2 for size in sizes):
        raise ValueError("sizes must contain integers >= 2")
    return sizes


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Regression Learning Curve",
        "",
        f"- engine: `{report['engine']}`",
        f"- train rows: `{report['data']['train_rows']}`",
        f"- validation rows: `{report['data']['validation_rows']}`",
        "- locked test: `never read`",
        "",
        "| Train rows | Variant | Brier mean | Brier stdev | Log loss | Accuracy |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for point in report["points"]:
        for variant, metrics in point["variants"].items():
            lines.append(
                f"| {point['train_rows']} | `{variant}` | {metrics['brier_mean']:.4f} | "
                f"{metrics['brier_stdev']:.4f} | {metrics['log_loss_mean']:.4f} | "
                f"{metrics['accuracy_mean']:.3f} |"
            )
    lines.extend(
        [
            "",
            f"Decision: **{report['decision']['recommendation']}**",
            "",
        ]
    )
    return "\n".join(lines)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
