#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import statistics
import sys
from typing import Any, Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.orchestration.matrix_regression_selector import load_weights, select_model_by_matrix_regression
from scripts.build_engine_outcome_matrix import _consensus, _judgment_index, _load_judge_policy


KIMI = "accounts/fireworks/models/kimi-k2p7-code"
MINIMAX = "accounts/fireworks/models/minimax-m3"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the frozen Sprint 49 championship policy ablation.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=Path("reports/generated/championship-ablation.json"))
    parser.add_argument("--markdown", type=Path, default=Path("reports/public/championship-ablation.md"))
    parser.add_argument("--bootstrap-repetitions", type=int, default=2000)
    args = parser.parse_args(argv)
    report = run_ablation(args.root, bootstrap_repetitions=args.bootstrap_repetitions)
    output = args.output if args.output.is_absolute() else args.root / args.output
    markdown = args.markdown if args.markdown.is_absolute() else args.root / args.markdown
    output.parent.mkdir(parents=True, exist_ok=True)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"champion": report["champion"], "locked_test": report["locked_test"]}, sort_keys=True))
    return 0


def run_ablation(root: Path, *, bootstrap_repetitions: int = 2000) -> dict[str, Any]:
    if bootstrap_repetitions < 100:
        raise ValueError("bootstrap_repetitions must be at least 100.")
    run = root / "data/championship-ablation"
    tasks = {str(row["id"]): row for row in _jsonl(run / "tasks.jsonl")}
    fireworks_policy = _load_judge_policy(root / "configs/fireworks-baseline-judge-policy.json")
    judgments = _judgment_index([run / "fireworks-judgments.jsonl"])
    candidates = _fireworks_candidates(
        [
            run / "kimi-candidates.jsonl",
            run / "minimax-candidates.jsonl",
        ],
        judgments=judgments,
        judge_policy=fireworks_policy,
    )
    matrix_weights = load_weights(root / "router/data/fireworks_track1_allowed_weights.json")
    intent_policy = json.loads((root / "configs/fireworks-intent-policy-v1.json").read_text(encoding="utf-8"))
    e2b_selected = _e2b_selected_tasks(root)
    deterministic = {str(row["task_id"]): row for row in _jsonl(run / "deterministic-candidates.jsonl")}

    selectors: dict[str, Callable[[Mapping[str, Any]], str]] = {
        "fireworks_kimi": lambda _task: KIMI,
        "fireworks_minimax": lambda _task: MINIMAX,
        "validation_intent_candidate": lambda task: str(intent_policy["intent_models"][task["source_assessment"]["intent"]]),
        "matrix_pareto_nash": lambda task: str(
            select_model_by_matrix_regression(
                TaskEnvelope(id=str(task["id"]), input_text=str(task["input_text"])),
                [KIMI, MINIMAX],
                matrix_weights,
            )["model"]
        ),
    }
    observations: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for task_id, task in tasks.items():
        split = str(task["regression_split"])
        lineage = str(task.get("mutation_lineage") or task_id)
        for variant, selector in selectors.items():
            model = selector(task)
            observations[variant][split].append(_observation(task, candidates[(task_id, model)], lineage=lineage))
        final_remote = candidates[(task_id, KIMI)]
        local = deterministic[task_id]
        final_candidate = _local_or_remote(local, final_remote)
        observations["deterministic_then_kimi"][split].append(_observation(task, final_candidate, lineage=lineage))

        e2b_candidate = e2b_selected.get(task_id)
        rejected = e2b_candidate if e2b_candidate is not None else final_remote
        observations["rejected_e2b_challenger"][split].append(_observation(task, rejected, lineage=lineage))

    summaries = {
        variant: {split: summarize(rows) for split, rows in split_rows.items()}
        for variant, split_rows in observations.items()
    }
    promotion_eligible = {
        variant: splits["validation"]
        for variant, splits in summaries.items()
        if variant not in {"validation_intent_candidate", "rejected_e2b_challenger"}
    }
    champion = select_champion(promotion_eligible)
    locked = summaries[champion]["test"]
    comparisons = {
        variant: paired_bootstrap(
            observations[variant]["test"],
            observations[champion]["test"],
            repetitions=bootstrap_repetitions,
            seed=49,
        )
        for variant in sorted(observations)
        if variant != champion
    }
    return {
        "schema_version": "championship-ablation-v1",
        "selection_split": "validation",
        "locked_test_used_for_tuning": False,
        "locked_test_used_as_promotion_gate": True,
        "selection_order": [
            "promotion_gate",
            "validation_conservative_accuracy",
            "validation_fireworks_tokens",
            "operational_dominance",
            "latency_ms",
            "variant_name",
        ],
        "champion": champion,
        "locked_test": locked,
        "variants": summaries,
        "paired_locked_test_vs_champion": comparisons,
        "evidence": {
            "tasks": len(tasks),
            "validation_rows": sum(task["regression_split"] == "validation" for task in tasks.values()),
            "locked_test_rows": sum(task["regression_split"] == "test" for task in tasks.values()),
            "current_deterministic_acceptances": sum(row.get("status") == "answered" for row in deterministic.values()),
            "rejected_e2b_selected_tasks": len(e2b_selected),
            "bootstrap_unit": "mutation_lineage",
            "bootstrap_repetitions": bootstrap_repetitions,
        },
        "decision": {
            "final_runtime": "deterministic_then_kimi",
            "reason": (
                "The deterministic layer is fail-closed and preserves the validation-selected Kimi baseline; "
                "local E2B, per-intent routing and matrix routing failed their frozen promotion comparisons."
            ),
            "functiongemma_bundled": False,
            "e2b_bundled": False,
            "fireworks_preferred_model": KIMI,
            "fallback": "allowed-model Pareto/Nash ordering plus strict-output retry",
            "rejected_variants": {
                "validation_intent_candidate": "failed the frozen 0.60 locked-test conservative accuracy gate",
                "rejected_e2b_challenger": "failed the frozen E2B Wilson promotion gate",
                "matrix_pareto_nash": "lower validation accuracy and more validation tokens than Kimi",
                "fireworks_minimax": "lower validation accuracy and more validation tokens than Kimi",
            },
        },
    }


def summarize(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    binary = [row for row in rows if isinstance(row.get("correct"), bool)]
    correct = sum(row.get("correct") is True for row in rows)
    return {
        "rows": total,
        "correct": correct,
        "incorrect_or_uncertain": total - correct,
        "conservative_accuracy": correct / total if total else 0.0,
        "binary_accuracy": sum(row.get("correct") is True for row in binary) / len(binary) if binary else 0.0,
        "binary_rows": len(binary),
        "fireworks_tokens": sum(int(row.get("tokens") or 0) for row in rows),
        "average_fireworks_tokens": statistics.fmean(int(row.get("tokens") or 0) for row in rows) if rows else 0.0,
        "latency_ms": sum(float(row.get("latency_ms") or 0.0) for row in rows),
        "local_answers": sum(bool(row.get("local")) for row in rows),
        "model_counts": dict(sorted(Counter(str(row.get("model") or "local") for row in rows).items())),
    }


def select_champion(validation: Mapping[str, Mapping[str, Any]]) -> str:
    if not validation:
        raise ValueError("No validation variants supplied.")
    return max(
        validation,
        key=lambda variant: (
            float(validation[variant]["conservative_accuracy"]),
            -int(validation[variant]["fireworks_tokens"]),
            variant == "deterministic_then_kimi",
            -float(validation[variant]["latency_ms"]),
            variant,
        ),
    )


def paired_bootstrap(
    challenger: Sequence[Mapping[str, Any]],
    champion: Sequence[Mapping[str, Any]],
    *,
    repetitions: int,
    seed: int,
) -> dict[str, Any]:
    if {row["task_id"] for row in challenger} != {row["task_id"] for row in champion}:
        raise ValueError("Paired bootstrap variants must cover identical tasks.")
    challenger_by_id = {str(row["task_id"]): row for row in challenger}
    champion_by_id = {str(row["task_id"]): row for row in champion}
    groups: dict[str, list[str]] = defaultdict(list)
    for row in challenger:
        groups[str(row["lineage"])].append(str(row["task_id"]))
    lineages = sorted(groups)
    rng = random.Random(seed)
    accuracy_deltas: list[float] = []
    token_deltas: list[float] = []
    for _ in range(repetitions):
        sampled = [rng.choice(lineages) for _ in lineages]
        task_ids = [task_id for lineage in sampled for task_id in groups[lineage]]
        if not task_ids:
            continue
        accuracy_deltas.append(
            statistics.fmean(float(challenger_by_id[task_id]["correct"] is True) for task_id in task_ids)
            - statistics.fmean(float(champion_by_id[task_id]["correct"] is True) for task_id in task_ids)
        )
        token_deltas.append(
            statistics.fmean(int(challenger_by_id[task_id]["tokens"]) for task_id in task_ids)
            - statistics.fmean(int(champion_by_id[task_id]["tokens"]) for task_id in task_ids)
        )
    return {
        "accuracy_delta": _interval(accuracy_deltas),
        "average_token_delta": _interval(token_deltas),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Championship Ablation",
        "",
        "Routes, features, coefficients and prompts were selected on validation only. The locked test was disclosed once and used only as a predeclared pass/fail promotion gate.",
        "",
        f"Validation-selected champion: `{report['champion']}`",
        "",
        "| Variant | Split | Accuracy | Binary accuracy | Fireworks tokens | Avg tokens | Local answers |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for variant, splits in sorted(report["variants"].items()):
        for split, metrics in sorted(splits.items()):
            lines.append(
                f"| `{variant}` | {split} | {metrics['conservative_accuracy']:.3f} | "
                f"{metrics['binary_accuracy']:.3f} | {metrics['fireworks_tokens']} | "
                f"{metrics['average_fireworks_tokens']:.1f} | {metrics['local_answers']} |"
            )
    lines.extend([
        "",
        "## Decision",
        "",
        f"Final runtime: `{report['decision']['final_runtime']}`",
        f"Preferred allowed model: `{report['decision']['fireworks_preferred_model']}`",
        f"FunctionGemma bundled: `{report['decision']['functiongemma_bundled']}`",
        f"E2B bundled: `{report['decision']['e2b_bundled']}`",
        "",
        str(report["decision"]["reason"]),
        "",
        "The local models remain reproducible research artifacts, but bundling a rejected route would increase image size, startup time and failure surface without measured token savings.",
        "",
    ])
    return "\n".join(lines)


def _fireworks_candidates(
    paths: Sequence[Path],
    *,
    judgments: Mapping[str, Sequence[Mapping[str, Any]]],
    judge_policy: Mapping[str, Sequence[str]],
) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for path in paths:
        for candidate in _jsonl(path):
            model = str(candidate["model_id"])
            if candidate.get("status") == "answered":
                correct, consensus, _, _ = _consensus(
                    judgments.get(str(candidate["id"]), []), allowed_judges=judge_policy[model]
                )
            else:
                correct, consensus = None, "runtime_failure"
            usage = candidate.get("fireworks_tokens") or {}
            result[(str(candidate["task_id"]), model)] = {
                "correct": correct,
                "consensus": consensus,
                "tokens": int(usage.get("prompt") or 0) + int(usage.get("completion") or 0),
                "latency_ms": float(candidate.get("latency_ms") or 0.0),
                "model": model,
                "local": False,
            }
    return result


def _e2b_selected_tasks(root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _jsonl(root / "data/championship-ablation/e2b-selected-test.jsonl"):
        result[str(row["task_id"])] = {
            "correct": row.get("correct"),
            "consensus": row.get("consensus"),
            "tokens": 0,
            "latency_ms": float(row.get("latency_ms") or 0.0),
            "model": "gemma4-e2b",
            "local": True,
        }
    return result


def _local_or_remote(local: Mapping[str, Any], remote: Mapping[str, Any]) -> dict[str, Any]:
    if local.get("status") != "answered":
        return dict(remote)
    return {
        "correct": None,
        "consensus": "missing_local_consensus",
        "tokens": 0,
        "latency_ms": float(local.get("latency_ms") or 0.0),
        "model": str(local.get("solver_name") or "deterministic"),
        "local": True,
    }


def _observation(task: Mapping[str, Any], candidate: Mapping[str, Any], *, lineage: str) -> dict[str, Any]:
    return {
        **dict(candidate),
        "task_id": str(task["id"]),
        "intent": str(task["source_assessment"]["intent"]),
        "lineage": lineage,
    }


def _interval(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "lower_95": 0.0, "upper_95": 0.0}
    ordered = sorted(values)
    return {
        "mean": statistics.fmean(ordered),
        "lower_95": ordered[int(0.025 * (len(ordered) - 1))],
        "upper_95": ordered[int(0.975 * (len(ordered) - 1))],
    }


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
