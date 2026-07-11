#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.fireworks_microbench import BenchTask, _load_env_files, _run_case
from router.orchestration.fireworks_model_router import normalize_fireworks_model_id
DEFAULT_MODELS = (
    "accounts/fireworks/models/minimax-m3",
    "accounts/fireworks/models/kimi-k2p7-code",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the sealed paired Fireworks Pareto v2 arena.")
    parser.add_argument("--tasks", type=Path, default=Path("evals/fireworks-pareto-v2/sealed/tasks.jsonl"))
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--base-url")
    parser.add_argument("--budget-usd", type=float, default=5.0)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/generated/fireworks-pareto-v2"))
    parser.add_argument("--report", type=Path, default=Path("reports/public/fireworks-pareto-v2.md"))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    _load_env_files((ROOT / ".env.fireworks", ROOT / ".env.fireworks.local"))
    api_key = os.getenv("FIREWORKS_API_KEY", "")
    if not api_key:
        raise SystemExit("FIREWORKS_API_KEY is not set")
    base_url = args.base_url or os.getenv("FIREWORKS_BASE_URL") or "https://api.fireworks.ai/inference/v1"
    models = tuple(normalize_fireworks_model_id(value) for value in args.models.split(",") if value.strip())
    allowed = {
        normalize_fireworks_model_id(value)
        for value in (os.getenv("ALLOWED_MODELS") or args.models).split(",") if value.strip()
    }
    if len(models) != 2 or not set(models).issubset(allowed):
        raise SystemExit("paired models must be present in ALLOWED_MODELS")
    result = run(
        ROOT / args.tasks, ROOT / args.output_dir, ROOT / args.report,
        models=models, allowed=allowed, base_url=base_url, api_key=api_key, budget=args.budget_usd,
    )
    if args.json:
        print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] or not args.check else 1


def run(tasks_path, output, report, *, models, allowed, base_url, api_key, budget):
    tasks = _tasks(tasks_path)
    output.mkdir(parents=True, exist_ok=True)
    results_path = output / "paired-results.jsonl"
    rows = _jsonl(results_path)
    completed = {(row["id"], row["model"]) for row in rows}
    spent = sum(float(row.get("estimated_cost_usd") or 0) for row in rows)
    policy_path = output / "frozen-policy.json"
    development = [task for task in tasks if task["split"] == "development"]
    sealed = [task for task in tasks if task["split"] == "sealed"]
    for split_tasks in (development, sealed):
        if split_tasks is sealed and not policy_path.exists():
            policy = _select_policy(rows, models)
            policy_path.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        for task in split_tasks:
            for model in models:
                if (task["id"], model) in completed:
                    continue
                if model not in allowed:
                    raise RuntimeError(f"model left ALLOWED_MODELS: {model}")
                if spent >= budget:
                    raise RuntimeError(f"hard budget reached before complete pairing: ${spent:.6f}")
                bench = BenchTask(task["id"], task["category"], task["tier"], task["prompt"], task["validator"])
                row = _run_case(
                    base_url=base_url, api_key=api_key, model=model, task=bench,
                    temperature=0.0, max_tokens=task["max_tokens"], timeout_s=90.0,
                    max_retries=1, reasoning_effort_override="none",
                )
                row.update({
                    "schema_version": "fireworks-pareto-v2-result-v1",
                    "category": task["category"], "difficulty": task["difficulty"],
                    "split": task["split"], "output_shape": task["output_shape"],
                    "prompt_sha256": task["prompt_sha256"], "mutation_lineage": task["mutation_lineage"],
                    "max_tokens": task["max_tokens"], "base_url": base_url,
                })
                spent += float(row.get("estimated_cost_usd") or 0)
                if spent > budget:
                    raise RuntimeError(f"hard budget exceeded: ${spent:.6f} > ${budget:.6f}")
                _append(results_path, row); rows.append(row); completed.add((task["id"], model))
                if len(rows) % 24 == 0:
                    print(json.dumps({"calls": len(rows), "valid": sum(r["valid"] for r in rows), "spent": spent}), flush=True)
    policy = json.loads(policy_path.read_text())
    result = analyze(tasks, rows, models, policy, budget)
    (output / "frontier.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(markdown(result), encoding="utf-8")
    return result


def analyze(tasks, rows, models, policy, budget):
    paired = _paired(rows)
    sealed = {task["id"] for task in tasks if task["split"] == "sealed"}
    development = {task["id"] for task in tasks if task["split"] == "development"}
    by_model = {model: _metrics([row for row in rows if row["model"] == model]) for model in models}
    by_category = {}
    for category in sorted({task["category"] for task in tasks}):
        by_category[category] = {
            model: _metrics([row for row in rows if row["model"] == model and row["category"] == category])
            for model in models
        }
    by_difficulty = {
        difficulty: {
            model: _metrics([row for row in rows if row["model"] == model and row["difficulty"] == difficulty])
            for model in models
        }
        for difficulty in sorted({task["difficulty"] for task in tasks})
    }
    by_output_shape = {
        shape: {
            model: _metrics([row for row in rows if row["model"] == model and row["output_shape"] == shape])
            for model in models
        }
        for shape in sorted({task["output_shape"] for task in tasks})
    }
    sealed_rows = [pair for task_id, pair in paired.items() if task_id in sealed]
    current_policy = json.loads((ROOT / "evals/fireworks-pareto-v2/baseline-policy.json").read_text())["intent_models"]
    policy_rows = [pair[policy["intent_models"][next(iter(pair.values()))["category"]]] for pair in sealed_rows]
    baseline_rows = [pair[models[1]] for pair in sealed_rows]
    current_rows = [pair[current_policy[next(iter(pair.values()))["category"]]] for pair in sealed_rows]
    policy_accuracy = sum(row["valid"] for row in policy_rows) / len(policy_rows)
    baseline_accuracy = sum(row["valid"] for row in baseline_rows) / len(baseline_rows)
    current_accuracy = sum(row["valid"] for row in current_rows) / len(current_rows)
    savings = [current["usage"]["total"] - selected["usage"]["total"] for current, selected in zip(current_rows, baseline_rows, strict=True)]
    sealed_lineages = [next(iter(pair.values()))["mutation_lineage"] for pair in sealed_rows]
    changed = [
        (saving, lineage)
        for saving, lineage, pair in zip(savings, sealed_lineages, sealed_rows, strict=True)
        if current_policy[next(iter(pair.values()))["category"]] != models[1]
    ]
    token_ci = _bootstrap_lineage_ci([item[0] for item in changed], [item[1] for item in changed])
    accuracy_delta = [float(pair[models[1]]["valid"]) - float(pair[models[0]]["valid"]) for pair in paired.values()]
    all_lineages = [next(iter(pair.values()))["mutation_lineage"] for pair in paired.values()]
    accuracy_delta_ci = _bootstrap_lineage_ci(accuracy_delta, all_lineages)
    game = _game_analysis(rows, models, development)
    spend = sum(float(row.get("estimated_cost_usd") or 0) for row in rows)
    complete_pairs = sum(1 for pair in paired.values() if set(pair) == set(models))
    checks = {
        "at_least_180_complete_pairs": complete_pairs >= 180,
        "base_url_and_allowed_models_only": all(row["base_url"].startswith("https://api.fireworks.ai/") and row["model"] in models for row in rows),
        "spend_at_most_5_usd": spend <= min(5.0, budget),
        "accuracy_regression_at_most_1pp": baseline_accuracy >= current_accuracy - .01,
        "positive_token_savings_ci95": token_ci[0] > 0,
        "preference_support_at_least_20": all(
            sum(1 for row in rows if row["split"] == "development" and row["category"] == category and row["model"] == model) >= 20
            for category, model in {category: models[1] for category in current_policy}.items()
        ),
        "policy_frozen_before_sealed_scoring": policy.get("selection_split") == "development",
    }
    return {
        "schema_version": "fireworks-pareto-v2-frontier-v1", "passed": all(checks.values()),
        "calls": len(rows), "complete_pairs": complete_pairs, "spend_usd": spend,
        "by_model": by_model, "by_category": by_category, "by_difficulty": by_difficulty,
        "by_output_shape": by_output_shape, "frozen_policy": policy,
        "current_policy": current_policy, "selected_policy": {category: models[1] for category in current_policy},
        "sealed_policy_accuracy": policy_accuracy, "sealed_kimi_accuracy": baseline_accuracy,
        "sealed_current_accuracy": current_accuracy,
        "sealed_mean_token_savings_vs_current": statistics.mean(savings), "token_savings_ci95": token_ci,
        "token_savings_ci95_scope": "sealed_changed_routes_grouped_by_mutation_lineage",
        "changed_route_rows": len(changed),
        "paired_kimi_minus_minimax_accuracy_delta": statistics.mean(accuracy_delta),
        "paired_accuracy_delta_ci95": accuracy_delta_ci,
        "game_theory": game, "checks": checks,
        "decision": "promote_always_kimi" if all(checks.values()) else "retain_existing_policy",
    }


def _select_policy(rows, models):
    intent_models = {}
    for category in sorted({row["category"] for row in rows if row["split"] == "development"}):
        choices = []
        for model in models:
            cohort = [row for row in rows if row["split"] == "development" and row["category"] == category and row["model"] == model]
            accuracy = sum(row["valid"] for row in cohort) / len(cohort)
            tokens = statistics.mean(row["usage"]["total"] for row in cohort)
            choices.append((-accuracy, tokens, model))
        intent_models[category] = min(choices)[2]
    return {"schema_version": "fireworks-pareto-v2-policy-v1", "selection_split": "development", "intent_models": intent_models}


def _game_analysis(rows, models, development):
    categories = sorted({row["category"] for row in rows})
    utilities = {model: {} for model in models}
    for model in models:
        for category in categories:
            cohort = [row for row in rows if row["id"] in development and row["model"] == model and row["category"] == category]
            accuracy = sum(row["valid"] for row in cohort) / len(cohort)
            tokens = statistics.mean(row["usage"]["total"] for row in cohort)
            utilities[model][category] = accuracy * 1000 - tokens / 1000
    best = {category: max(utilities[model][category] for model in models) for category in categories}
    regrets = {model: max(best[c] - utilities[model][c] for c in categories) for model in models}
    grid = []
    for step in range(101):
        p = step / 100
        worst = max(best[c] - (p * utilities[models[0]][c] + (1-p) * utilities[models[1]][c]) for c in categories)
        grid.append((worst, p))
    worst, p = min(grid)
    return {"utilities": utilities, "pure_minimax_regret": regrets, "nash_minimax_mix": {models[0]: p, models[1]: 1-p}, "mixed_max_regret": worst}


def _bootstrap_mean_ci(values, repeats=4000):
    rng = random.Random(66066)
    means = sorted(statistics.mean(rng.choice(values) for _ in values) for _ in range(repeats))
    return [means[int(.025 * repeats)], means[int(.975 * repeats)]]


def _bootstrap_lineage_ci(values, lineages, repeats=4000):
    grouped = defaultdict(list)
    for value, lineage in zip(values, lineages, strict=True):
        grouped[lineage].append(value)
    lineage_means = [statistics.mean(group) for group in grouped.values()]
    return _bootstrap_mean_ci(lineage_means, repeats)


def _metrics(rows):
    return {"calls": len(rows), "correct": sum(row["valid"] for row in rows), "accuracy": sum(row["valid"] for row in rows)/len(rows), "prompt_tokens": sum(row["usage"]["prompt"] for row in rows), "completion_tokens": sum(row["usage"]["completion"] for row in rows), "total_tokens": sum(row["usage"]["total"] for row in rows), "mean_latency_ms": statistics.mean(row["latency_ms"] for row in rows)}


def _paired(rows):
    result = defaultdict(dict)
    for row in rows: result[row["id"]][row["model"]] = row
    return result


def _tasks(path):
    return _jsonl(path)


def _jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def _append(path, row):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n"); handle.flush(); os.fsync(handle.fileno())


def markdown(result):
    lines = ["# Fireworks Pareto Arena v2", "", f"Decision: `{result['decision']}`", "", f"- Calls: `{result['calls']}`", f"- Complete pairs: `{result['complete_pairs']}`", f"- Estimated spend: `${result['spend_usd']:.6f}`", f"- Frozen-policy sealed accuracy: `{result['sealed_policy_accuracy']:.2%}`", f"- Current-policy sealed accuracy: `{result['sealed_current_accuracy']:.2%}`", f"- Always-Kimi sealed accuracy: `{result['sealed_kimi_accuracy']:.2%}`", f"- Mean sealed token savings versus current: `{result['sealed_mean_token_savings_vs_current']:.2f}`", f"- Token savings CI95: `{result['token_savings_ci95'][0]:.2f}` to `{result['token_savings_ci95'][1]:.2f}`", "", "## Gates", ""]
    lines.extend(f"- [{'x' if value else ' '}] `{name}`" for name, value in result["checks"].items())
    lines.extend(["", "## Selected Category Policy", ""])
    lines.extend(f"- `{category}`: `{model}`" for category, model in result["selected_policy"].items())
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
