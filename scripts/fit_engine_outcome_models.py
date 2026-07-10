#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from router.orchestration.matrix_regression_selector import _ridge_regression


SIMPLICITY_TOLERANCE = 0.005
NONLINEAR_FEATURES = (
    "square.score.deterministic_fit",
    "square.score.reasoning_demand",
    "square.score.knowledge_uncertainty",
    "square.score.generation_demand",
    "square.score.format_complexity",
    "interaction.reasoning_x_format",
    "interaction.generation_x_format",
    "interaction.input_length_x_generation",
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Fit lineage-held-out outcome models from the engine matrix.")
    root.add_argument("--matrix", type=Path, required=True)
    root.add_argument("--output", type=Path, required=True)
    root.add_argument("--report", type=Path, required=True)
    root.add_argument("--folds", type=int, default=5)
    root.add_argument("--l2", type=float, default=0.75)
    root.add_argument("--ridge-lambda", type=float, default=1.0)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    report = fit_outcome_models(
        matrix_path=args.matrix,
        folds=args.folds,
        l2=args.l2,
        ridge_lambda=args.ridge_lambda,
    )
    _write_json(args.output, report)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


def fit_outcome_models(
    *,
    matrix_path: Path,
    folds: int = 5,
    l2: float = 0.75,
    ridge_lambda: float = 1.0,
) -> dict[str, Any]:
    if folds < 2 or l2 < 0 or ridge_lambda <= 0:
        raise ValueError("folds must be >= 2, l2 non-negative and ridge_lambda positive.")
    rows = _jsonl(matrix_path)
    answered = [row for row in rows if row.get("status") == "answered"]
    split_strategy = _split_strategy(answered)
    fixed_splits = split_strategy == "fixed_train_validation_test"
    engines = sorted({str(row.get("model_id") or row["engine"]) for row in answered})
    models: dict[str, Any] = {}
    for engine in engines:
        engine_rows = [row for row in answered if str(row.get("model_id") or row["engine"]) == engine]
        labeled = [row for row in engine_rows if isinstance(row.get("correct"), bool)]
        if not labeled:
            continue
        feature_names = _feature_names(labeled)
        correctness = _fit_correctness(
            labeled, feature_names, folds=folds, l2=l2, fixed_splits=fixed_splits
        )
        latency = _fit_continuous(
            engine_rows,
            feature_names,
            target=lambda row: float(row["latency_ms"]),
            folds=folds,
            ridge_lambda=ridge_lambda,
            fixed_splits=fixed_splits,
        )
        prompt_tokens = _fit_continuous(
            engine_rows,
            feature_names,
            target=lambda row: float(row["fireworks_prompt_tokens"]),
            folds=folds,
            ridge_lambda=ridge_lambda,
            fixed_splits=fixed_splits,
        )
        completion_tokens = _fit_continuous(
            engine_rows,
            feature_names,
            target=lambda row: float(row["fireworks_completion_tokens"]),
            folds=folds,
            ridge_lambda=ridge_lambda,
            fixed_splits=fixed_splits,
        )
        failures = sum(bool(row.get("runtime_failure")) for row in engine_rows)
        memory_values = [float(row["peak_memory_mb"]) for row in engine_rows if row.get("memory_observed")]
        models[engine] = {
            "rows": len(engine_rows),
            "binary_correctness_rows": len(labeled),
            "lineages": len({_group(row) for row in labeled}),
            "correctness": correctness,
            "latency_ms": latency,
            "fireworks_prompt_tokens": prompt_tokens,
            "fireworks_completion_tokens": completion_tokens,
            "runtime_failure": {
                "model": "laplace_constant",
                "observed_failures": failures,
                "observations": len(engine_rows),
                "probability": (failures + 1) / (len(engine_rows) + 2),
            },
            "peak_memory_mb": {
                "model": "observed_constant" if memory_values else "not_observed",
                "value": max(memory_values) if memory_values else None,
            },
        }
    return {
        "schema_version": "engine-outcome-models-v1",
        "matrix_sha256": _sha256(matrix_path),
        "fit_config": {
            "folds": folds,
            "split_strategy": split_strategy,
            "group_key": "regression_split" if fixed_splits else "mutation_lineage",
            "l2": l2,
            "ridge_lambda": ridge_lambda,
            "simplicity_tolerance_brier": SIMPLICITY_TOLERANCE,
        },
        "summary": {
            "matrix_rows": len(rows),
            "answered_rows": len(answered),
            "fitted_engines": len(models),
            "split_counts": {
                split: sum(row.get("regression_split") == split for row in answered)
                for split in ("train", "validation", "test")
            } if fixed_splits else {},
        },
        "models": models,
    }


def _fit_correctness(
    rows: Sequence[Mapping[str, Any]],
    feature_names: Sequence[str],
    *,
    folds: int,
    l2: float,
    fixed_splits: bool = False,
) -> dict[str, Any]:
    if fixed_splits:
        return _fit_correctness_fixed(rows, feature_names, l2=l2)
    variants = ("constant", "logistic_linear", "logistic_nonlinear")
    predictions: dict[str, list[tuple[float, float]]] = {name: [] for name in variants}
    assignments = [_fold(_group(row), folds) for row in rows]
    for fold in range(folds):
        train = [row for row, assigned in zip(rows, assignments, strict=True) if assigned != fold]
        test = [row for row, assigned in zip(rows, assignments, strict=True) if assigned == fold]
        if not train or not test:
            continue
        y_train = [float(bool(row["correct"])) for row in train]
        prior = (sum(y_train) + 1) / (len(y_train) + 2)
        for row in test:
            predictions["constant"].append((float(bool(row["correct"])), prior))
        for variant, nonlinear in (("logistic_linear", False), ("logistic_nonlinear", True)):
            x_train = [_design(row, feature_names, nonlinear=nonlinear) for row in train]
            weights = _logistic_fit(x_train, y_train, l2=l2)
            for row in test:
                prediction = _sigmoid(_dot(weights, _design(row, feature_names, nonlinear=nonlinear)))
                predictions[variant].append((float(bool(row["correct"])), prediction))
    metrics = {name: _binary_metrics(values) for name, values in predictions.items()}
    selected = _select_simple(metrics)
    nonlinear = selected == "logistic_nonlinear"
    if selected == "constant":
        weights = [(sum(bool(row["correct"]) for row in rows) + 1) / (len(rows) + 2)]
        selected_features = ["probability"]
    else:
        weights = _logistic_fit(
            [_design(row, feature_names, nonlinear=nonlinear) for row in rows],
            [float(bool(row["correct"])) for row in rows],
            l2=l2,
        )
        selected_features = ["bias", *feature_names, *(NONLINEAR_FEATURES if nonlinear else ())]
    return {
        "selected_model": selected,
        "feature_names": selected_features,
        "coefficients": weights,
        "observed_prevalence": sum(bool(row["correct"]) for row in rows) / len(rows),
        "held_out_metrics": metrics,
        "calibration_bins": _calibration_bins(predictions[selected]),
    }


def _fit_continuous(
    rows: Sequence[Mapping[str, Any]],
    feature_names: Sequence[str],
    *,
    target: Any,
    folds: int,
    ridge_lambda: float,
    fixed_splits: bool = False,
) -> dict[str, Any]:
    if fixed_splits:
        return _fit_continuous_fixed(
            rows,
            feature_names,
            target=target,
            ridge_lambda=ridge_lambda,
        )
    assignments = [_fold(_group(row), folds) for row in rows]
    predictions: dict[str, list[tuple[float, float]]] = {"constant": [], "ridge_log1p": []}
    for fold in range(folds):
        train = [row for row, assigned in zip(rows, assignments, strict=True) if assigned != fold]
        test = [row for row, assigned in zip(rows, assignments, strict=True) if assigned == fold]
        if not train or not test:
            continue
        baseline = statistics.median(target(row) for row in train)
        x_train = [[1.0, *_values(row, feature_names)] for row in train]
        y_train = [math.log1p(max(0.0, target(row))) for row in train]
        coefficients = _ridge_regression(x_train, y_train, ridge_lambda)
        for row in test:
            actual = max(0.0, target(row))
            predictions["constant"].append((actual, baseline))
            estimate = max(0.0, math.expm1(_dot(coefficients, [1.0, *_values(row, feature_names)])))
            predictions["ridge_log1p"].append((actual, estimate))
    metrics = {name: _continuous_metrics(values) for name, values in predictions.items()}
    selected = "ridge_log1p" if metrics["ridge_log1p"]["mae"] < metrics["constant"]["mae"] * 0.95 else "constant"
    if selected == "ridge_log1p":
        coefficients = _ridge_regression(
            [[1.0, *_values(row, feature_names)] for row in rows],
            [math.log1p(max(0.0, target(row))) for row in rows],
            ridge_lambda,
        )
        names = ["bias", *feature_names]
    else:
        coefficients = [statistics.median(target(row) for row in rows)]
        names = ["constant"]
    return {
        "selected_model": selected,
        "feature_names": names,
        "coefficients": coefficients,
        "held_out_metrics": metrics,
    }


def _fit_correctness_fixed(
    rows: Sequence[Mapping[str, Any]],
    feature_names: Sequence[str],
    *,
    l2: float,
) -> dict[str, Any]:
    train, validation, test = _partition_fixed(rows)
    variants = ("constant", "logistic_linear", "logistic_nonlinear")
    validation_metrics: dict[str, dict[str, float]] = {}
    for variant in variants:
        coefficients, _ = _fit_binary_variant(train, feature_names, variant=variant, l2=l2)
        validation_metrics[variant] = _binary_metrics(
            [
                (float(bool(row["correct"])), _predict_binary_variant(row, feature_names, variant, coefficients))
                for row in validation
            ]
        )
    selected = _select_simple(validation_metrics)
    selected_coefficients, _ = _fit_binary_variant(
        train, feature_names, variant=selected, l2=l2
    )
    selected_validation_pairs = [
        (
            float(bool(row["correct"])),
            _predict_binary_variant(
                row, feature_names, selected, selected_coefficients
            ),
        )
        for row in validation
    ]
    development = [*train, *validation]
    coefficients, selected_features = _fit_binary_variant(
        development, feature_names, variant=selected, l2=l2
    )
    locked_test_metrics: dict[str, dict[str, float]] = {}
    for variant in variants:
        test_coefficients, _ = _fit_binary_variant(
            development, feature_names, variant=variant, l2=l2
        )
        locked_test_metrics[variant] = _binary_metrics(
            [
                (float(bool(row["correct"])), _predict_binary_variant(row, feature_names, variant, test_coefficients))
                for row in test
            ]
        )
    return {
        "selected_model": selected,
        "feature_names": selected_features,
        "coefficients": coefficients,
        "observed_prevalence": sum(bool(row["correct"]) for row in development) / len(development),
        "held_out_metrics": validation_metrics,
        "selection_metrics": validation_metrics,
        "locked_test_metrics": locked_test_metrics,
        "calibration_bins": _calibration_bins(selected_validation_pairs),
        "split_rows": {
            "train": len(train),
            "validation": len(validation),
            "test": len(test),
        },
    }


def _fit_binary_variant(
    rows: Sequence[Mapping[str, Any]],
    feature_names: Sequence[str],
    *,
    variant: str,
    l2: float,
) -> tuple[list[float], list[str]]:
    if variant == "constant":
        probability = (sum(bool(row["correct"]) for row in rows) + 1) / (len(rows) + 2)
        return [probability], ["probability"]
    nonlinear = variant == "logistic_nonlinear"
    if variant not in {"logistic_linear", "logistic_nonlinear"}:
        raise ValueError(f"Unsupported binary model variant {variant!r}.")
    coefficients = _logistic_fit(
        [_design(row, feature_names, nonlinear=nonlinear) for row in rows],
        [float(bool(row["correct"])) for row in rows],
        l2=l2,
    )
    names = ["bias", *feature_names, *(NONLINEAR_FEATURES if nonlinear else ())]
    return coefficients, names


def _predict_binary_variant(
    row: Mapping[str, Any],
    feature_names: Sequence[str],
    variant: str,
    coefficients: Sequence[float],
) -> float:
    if variant == "constant":
        return float(coefficients[0])
    return _sigmoid(
        _dot(
            coefficients,
            _design(row, feature_names, nonlinear=variant == "logistic_nonlinear"),
        )
    )


def _fit_continuous_fixed(
    rows: Sequence[Mapping[str, Any]],
    feature_names: Sequence[str],
    *,
    target: Any,
    ridge_lambda: float,
) -> dict[str, Any]:
    train, validation, test = _partition_fixed(rows)
    variants = ("constant", "ridge_log1p")
    validation_metrics: dict[str, dict[str, float]] = {}
    for variant in variants:
        coefficients, _ = _fit_continuous_variant(
            train, feature_names, target=target, variant=variant, ridge_lambda=ridge_lambda
        )
        validation_metrics[variant] = _continuous_metrics(
            [
                (max(0.0, target(row)), _predict_continuous_variant(row, feature_names, variant, coefficients))
                for row in validation
            ]
        )
    selected = (
        "ridge_log1p"
        if validation_metrics["ridge_log1p"]["mae"] < validation_metrics["constant"]["mae"] * 0.95
        else "constant"
    )
    development = [*train, *validation]
    coefficients, names = _fit_continuous_variant(
        development,
        feature_names,
        target=target,
        variant=selected,
        ridge_lambda=ridge_lambda,
    )
    locked_test_metrics: dict[str, dict[str, float]] = {}
    for variant in variants:
        test_coefficients, _ = _fit_continuous_variant(
            development,
            feature_names,
            target=target,
            variant=variant,
            ridge_lambda=ridge_lambda,
        )
        locked_test_metrics[variant] = _continuous_metrics(
            [
                (max(0.0, target(row)), _predict_continuous_variant(row, feature_names, variant, test_coefficients))
                for row in test
            ]
        )
    return {
        "selected_model": selected,
        "feature_names": names,
        "coefficients": coefficients,
        "held_out_metrics": validation_metrics,
        "selection_metrics": validation_metrics,
        "locked_test_metrics": locked_test_metrics,
        "split_rows": {
            "train": len(train),
            "validation": len(validation),
            "test": len(test),
        },
    }


def _fit_continuous_variant(
    rows: Sequence[Mapping[str, Any]],
    feature_names: Sequence[str],
    *,
    target: Any,
    variant: str,
    ridge_lambda: float,
) -> tuple[list[float], list[str]]:
    if variant == "constant":
        return [statistics.median(target(row) for row in rows)], ["constant"]
    if variant != "ridge_log1p":
        raise ValueError(f"Unsupported continuous model variant {variant!r}.")
    coefficients = _ridge_regression(
        [[1.0, *_values(row, feature_names)] for row in rows],
        [math.log1p(max(0.0, target(row))) for row in rows],
        ridge_lambda,
    )
    return coefficients, ["bias", *feature_names]


def _predict_continuous_variant(
    row: Mapping[str, Any],
    feature_names: Sequence[str],
    variant: str,
    coefficients: Sequence[float],
) -> float:
    if variant == "constant":
        return max(0.0, float(coefficients[0]))
    return max(
        0.0,
        math.expm1(_dot(coefficients, [1.0, *_values(row, feature_names)])),
    )


def _select_simple(metrics: Mapping[str, Mapping[str, float]]) -> str:
    best = min(metrics, key=lambda name: metrics[name]["brier"])
    if metrics["constant"]["brier"] <= metrics[best]["brier"] + SIMPLICITY_TOLERANCE:
        return "constant"
    if metrics["logistic_linear"]["brier"] <= metrics[best]["brier"] + SIMPLICITY_TOLERANCE:
        return "logistic_linear"
    return "logistic_nonlinear"


def _logistic_fit(x: Sequence[Sequence[float]], y: Sequence[float], *, l2: float) -> list[float]:
    if not x or len(x) != len(y):
        raise ValueError("Logistic fit requires aligned non-empty observations.")
    weights = [0.0] * len(x[0])
    for iteration in range(1600):
        gradient = [0.0] * len(weights)
        for row, target in zip(x, y, strict=True):
            error = _sigmoid(_dot(weights, row)) - target
            for index, value in enumerate(row):
                gradient[index] += error * value
        scale = 1.0 / len(x)
        for index in range(len(weights)):
            regularization = 0.0 if index == 0 else l2 * weights[index]
            gradient[index] = gradient[index] * scale + regularization * scale
        learning_rate = 0.35 / math.sqrt(1.0 + iteration / 100.0)
        for index in range(len(weights)):
            weights[index] -= learning_rate * gradient[index]
    return weights


def _design(row: Mapping[str, Any], feature_names: Sequence[str], *, nonlinear: bool) -> list[float]:
    values = _values(row, feature_names)
    if not nonlinear:
        return [1.0, *values]
    by_name = dict(zip(feature_names, values, strict=True))
    score = lambda name: by_name.get(f"score.{name}", 0.0)
    extra = [
        score("deterministic_fit") ** 2,
        score("reasoning_demand") ** 2,
        score("knowledge_uncertainty") ** 2,
        score("generation_demand") ** 2,
        score("format_complexity") ** 2,
        score("reasoning_demand") * score("format_complexity"),
        score("generation_demand") * score("format_complexity"),
        by_name.get("struct.input_tokens_log", 0.0) * score("generation_demand"),
    ]
    return [1.0, *values, *extra]


def _feature_names(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    names = list(rows[0]["features"]["names"])
    if any(list(row["features"]["names"]) != names for row in rows):
        raise ValueError("Matrix feature vectors use inconsistent schemas.")
    return names


def _split_strategy(rows: Sequence[Mapping[str, Any]]) -> str:
    values = [row.get("regression_split") for row in rows]
    if not values or all(value is None for value in values):
        return "lineage_grouped_cross_validation"
    if any(value not in {"train", "validation", "test"} for value in values):
        raise ValueError("Matrix must use either complete fixed splits or no fixed splits.")
    present = set(values)
    if present != {"train", "validation", "test"}:
        raise ValueError("Fixed regression matrix requires non-empty train, validation and test splits.")
    return "fixed_train_validation_test"


def _partition_fixed(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    if _split_strategy(rows) != "fixed_train_validation_test":
        raise ValueError("Fixed fitting requires explicit train, validation and test rows.")
    train = [row for row in rows if row.get("regression_split") == "train"]
    validation = [row for row in rows if row.get("regression_split") == "validation"]
    test = [row for row in rows if row.get("regression_split") == "test"]
    return train, validation, test


def _values(row: Mapping[str, Any], names: Sequence[str]) -> list[float]:
    if list(row["features"]["names"]) != list(names):
        raise ValueError("Feature order mismatch.")
    return [float(value) for value in row["features"]["values"]]


def _binary_metrics(pairs: Sequence[tuple[float, float]]) -> dict[str, float]:
    if not pairs:
        return {"observations": 0.0, "brier": 1.0, "log_loss": 99.0, "accuracy": 0.0}
    clipped = [(actual, min(1 - 1e-9, max(1e-9, predicted))) for actual, predicted in pairs]
    return {
        "observations": float(len(pairs)),
        "brier": sum((predicted - actual) ** 2 for actual, predicted in clipped) / len(clipped),
        "log_loss": -sum(actual * math.log(predicted) + (1 - actual) * math.log(1 - predicted) for actual, predicted in clipped) / len(clipped),
        "accuracy": sum((predicted >= 0.5) == bool(actual) for actual, predicted in clipped) / len(clipped),
    }


def _calibration_bins(
    pairs: Sequence[tuple[float, float]],
    *,
    maximum_bins: int = 5,
) -> list[dict[str, float]]:
    if maximum_bins < 1 or not pairs:
        return []
    ordered = sorted(pairs, key=lambda pair: pair[1])
    unique_predictions = len({round(predicted, 12) for _, predicted in ordered})
    bin_count = min(maximum_bins, max(1, len(ordered) // 20), unique_predictions)
    result: list[dict[str, float]] = []
    for index in range(bin_count):
        start = index * len(ordered) // bin_count
        end = (index + 1) * len(ordered) // bin_count
        bucket = ordered[start:end]
        successes = sum(actual for actual, _ in bucket)
        observations = len(bucket)
        rate = successes / observations
        z = 1.959963984540054
        denominator = 1.0 + z * z / observations
        center = rate + z * z / (2.0 * observations)
        margin = z * math.sqrt(
            rate * (1.0 - rate) / observations
            + z * z / (4.0 * observations * observations)
        )
        result.append(
            {
                "prediction_min": min(predicted for _, predicted in bucket),
                "prediction_max": max(predicted for _, predicted in bucket),
                "observations": float(observations),
                "empirical_accuracy": rate,
                "wilson_lower_95": max(0.0, (center - margin) / denominator),
            }
        )
    return result


def _continuous_metrics(pairs: Sequence[tuple[float, float]]) -> dict[str, float]:
    if not pairs:
        return {"observations": 0.0, "mae": math.inf, "rmse": math.inf}
    return {
        "observations": float(len(pairs)),
        "mae": sum(abs(predicted - actual) for actual, predicted in pairs) / len(pairs),
        "rmse": math.sqrt(sum((predicted - actual) ** 2 for actual, predicted in pairs) / len(pairs)),
    }


def _group(row: Mapping[str, Any]) -> str:
    return str(row.get("mutation_lineage") or f"task:{row['task_id']}")


def _fold(group: str, folds: int) -> int:
    return int(hashlib.sha256(group.encode("utf-8")).hexdigest()[:8], 16) % folds


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-min(value, 60.0)))
    exp_value = math.exp(max(value, -60.0))
    return exp_value / (1.0 + exp_value)


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def render_markdown(report: Mapping[str, Any]) -> str:
    fixed = report["fit_config"].get("split_strategy") == "fixed_train_validation_test"
    split_description = (
        "fixed train/validation/locked-test split"
        if fixed
        else f"{report['fit_config']['folds']} folds grouped by mutation lineage"
    )
    lines = [
        "# Engine Outcome Regression Report",
        "",
        f"- matrix rows: `{report['summary']['matrix_rows']}`",
        f"- answered rows: `{report['summary']['answered_rows']}`",
        f"- fitted engines: `{report['summary']['fitted_engines']}`",
        f"- split: `{split_description}`",
        "",
        "| Engine | Binary rows | Correct rate | Selected correctness | Brier | Selected latency | Latency MAE ms |",
        "| --- | ---: | ---: | --- | ---: | --- | ---: |",
    ]
    for engine, model in report["models"].items():
        correctness = model["correctness"]
        selected_correctness = correctness["selected_model"]
        brier = correctness["held_out_metrics"][selected_correctness]["brier"]
        latency = model["latency_ms"]
        selected_latency = latency["selected_model"]
        latency_mae = latency["held_out_metrics"][selected_latency]["mae"]
        lines.append(
            f"| `{engine}` | {model['binary_correctness_rows']} | {correctness['observed_prevalence']:.3f} | "
            f"`{selected_correctness}` | {brier:.4f} | `{selected_latency}` | {latency_mae:.1f} |"
        )
    lines.extend([
        "",
        (
            "Teacher disagreements are excluded from binary correctness fitting, not coerced to failure. "
            + (
                "Model selection uses validation only; selected coefficients are refit on train plus validation, and locked-test metrics are disclosed without influencing selection. "
                if fixed
                else "Every held-out fold is separated by mutation lineage. "
            )
            + "The nonlinear challenger is promoted only when its Brier score beats simpler alternatives beyond the configured tolerance."
        ),
        "",
    ])
    return "\n".join(lines)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
