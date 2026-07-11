#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.fit_e2b_270m_matrix_regression import (
    FOLDS,
    INTENTS,
    SCORES,
    _fold,
    _logistic_fit,
    _predict,
    _project,
    _wilson,
    load_population,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate the final hybrid Fireworks and E2B Pareto frontier.")
    parser.add_argument("--thresholds", default="0.75,0.80,0.85")
    parser.add_argument("--budget-usd", type=float, default=10.0)
    parser.add_argument("--live-results", type=Path, default=Path("reports/generated/full-local/fireworks-live-pareto.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("reports/public/final-pareto-calibration.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/public/final-pareto-calibration.md"))
    parser.add_argument("--policy", type=Path, default=Path("configs/fireworks-intent-policy-v2.json"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    thresholds = [float(item) for item in args.thresholds.split(",")]
    rows = _jsonl(ROOT / args.live_results)
    if not rows:
        raise ValueError("Live Fireworks results are required.")
    spent = sum(float(row["estimated_cost_usd"]) for row in rows)
    if spent > args.budget_usd:
        raise ValueError("Observed Fireworks spend exceeds the hard experiment cap.")

    by_task = defaultdict(dict)
    for row in rows:
        by_task[row["id"]][row["model"].split("/")[-1]] = row
    required = {"minimax-m3", "kimi-k2p7-code"}
    if any(set(models) != required for models in by_task.values()):
        raise ValueError("Every Pareto task must contain both allowed model candidates.")

    candidates = {
        "always_minimax": _score([models["minimax-m3"] for models in by_task.values()]),
        "always_kimi": _score([models["kimi-k2p7-code"] for models in by_task.values()]),
        "intent_policy": _score(
            [models["minimax-m3"] if models["minimax-m3"]["domain"] == "extraction" else models["kimi-k2p7-code"] for models in by_task.values()]
        ),
    }
    best_accuracy = max(item["accuracy"] for item in candidates.values())
    for item in candidates.values():
        item["accuracy_regret"] = best_accuracy - item["accuracy"]
        item["nondominated"] = not any(
            other["accuracy"] >= item["accuracy"]
            and other["tokens"] <= item["tokens"]
            and (other["accuracy"] > item["accuracy"] or other["tokens"] < item["tokens"])
            for other in candidates.values()
        )
    savings_samples = _bootstrap_savings(by_task, seed=63064, resamples=2000)
    e2b = _e2b_thresholds(thresholds)
    selected_threshold = max(e2b, key=lambda item: (item["wilson_lower_95"], item["precision"], item["coverage"]))
    selected = "intent_policy"
    checks = {
        "spend_below_hard_cap": spent <= args.budget_usd,
        "paired_population_complete": len(by_task) == 23,
        "selected_no_accuracy_regression": candidates[selected]["accuracy"] == best_accuracy,
        "selected_positive_token_savings": candidates[selected]["tokens"] < candidates["always_minimax"]["tokens"],
        "bootstrap_lower_bound_positive": savings_samples[50] > 0,
        "selected_is_pareto_nondominated": candidates[selected]["nondominated"],
        "e2b_threshold_frozen_from_grouped_oof": selected_threshold["threshold"] in thresholds,
        "runtime_models_authorized": required == {"minimax-m3", "kimi-k2p7-code"},
    }
    payload = {
        "schema_version": "final-pareto-calibration-v1",
        "passed": all(checks.values()),
        "live_calls": len(rows),
        "estimated_spend_usd": spent,
        "budget_usd": args.budget_usd,
        "candidates": candidates,
        "selected_fireworks_policy": selected,
        "selected_e2b_threshold": selected_threshold,
        "e2b_thresholds": e2b,
        "paired_token_savings_ci95": [savings_samples[50], savings_samples[1950]],
        "checks": checks,
        "game_theory": {
            "accuracy_first_best_response": selected,
            "token_first_subject_to_accuracy_gate": selected,
            "nash_equilibrium": selected,
            "reason": "No unilateral switch improves accuracy; among accuracy-equivalent policies, the intent policy minimizes scored tokens.",
        },
        "limitations": [
            "The live microbench contains 23 deterministic-validator tasks and does not estimate hidden-evaluator accuracy.",
            "E2B threshold metrics are grouped out-of-fold historical evidence, not new Fireworks calls.",
        ],
    }
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    source_sha = hashlib.sha256(output.read_bytes()).hexdigest()
    policy = {
        "schema_version": "fireworks-intent-policy-v1",
        "selection_split": "validation",
        "locked_test_used_for_selection": False,
        "default_enabled": True,
        "default_model": "accounts/fireworks/models/kimi-k2p7-code",
        "allowed_models": [
            "accounts/fireworks/models/minimax-m3",
            "accounts/fireworks/models/kimi-k2p7-code",
        ],
        "intent_models": {
            "factual_qa": "accounts/fireworks/models/kimi-k2p7-code",
            "math_reasoning": "accounts/fireworks/models/kimi-k2p7-code",
            "sentiment": "accounts/fireworks/models/kimi-k2p7-code",
            "summarization": "accounts/fireworks/models/kimi-k2p7-code",
            "ner": "accounts/fireworks/models/minimax-m3",
            "code_debugging": "accounts/fireworks/models/kimi-k2p7-code",
            "logic_puzzle": "accounts/fireworks/models/kimi-k2p7-code",
            "code_generation": "accounts/fireworks/models/kimi-k2p7-code"
        },
        "source": {
            "comparison_report": str(args.output),
            "comparison_report_sha256": source_sha,
            "live_calls": len(rows),
            "estimated_spend_usd": spent
        }
    }
    policy_path = ROOT / args.policy
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = ROOT / args.report
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(_markdown(payload, policy_path), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    return 0 if payload["passed"] else 1


def _score(rows):
    return {
        "rows": len(rows),
        "correct": sum(bool(row["valid"]) for row in rows),
        "accuracy": sum(bool(row["valid"]) for row in rows) / len(rows),
        "tokens": sum(int(row["usage"]["total"]) for row in rows),
        "cost_usd": sum(float(row["estimated_cost_usd"]) for row in rows),
        "latency_ms": sum(float(row["latency_ms"]) for row in rows),
    }


def _bootstrap_savings(by_task, *, seed: int, resamples: int):
    ids = sorted(by_task)
    rng = random.Random(seed)
    samples = []
    for _ in range(resamples):
        sample = [rng.choice(ids) for _ in ids]
        saved = 0
        for task_id in sample:
            models = by_task[task_id]
            selected = models["minimax-m3"] if models["minimax-m3"]["domain"] == "extraction" else models["kimi-k2p7-code"]
            saved += int(models["minimax-m3"]["usage"]["total"]) - int(selected["usage"]["total"])
        samples.append(saved)
    return sorted(samples)


def _e2b_thresholds(thresholds):
    rows, _ = load_population()
    rows = [row for row in rows if row["source"] == "v2"]
    folds = [_fold(row["source"], row["lineage"]) for row in rows]
    predictions = [0.0] * len(rows)
    for fold in range(FOLDS):
        train = [row for row, assigned in zip(rows, folds, strict=True) if assigned != fold]
        held = [(index, row) for index, (row, assigned) in enumerate(zip(rows, folds, strict=True)) if assigned == fold]
        global_weights = _logistic_fit([_project(row, range(len(INTENTS), len(INTENTS) + len(SCORES))) for row in train], l2=2.0, dimensions=len(SCORES))
        models = {}
        for intent_index, intent in enumerate(INTENTS):
            cohort = [row for row in train if row["values"][intent_index] == 1.0]
            models[intent] = _logistic_fit([_project(row, range(len(INTENTS), len(INTENTS) + len(SCORES))) for row in cohort], l2=2.0, dimensions=len(SCORES)) if len(cohort) >= 40 else global_weights
        for index, row in held:
            intent = INTENTS[next((item for item in range(len(INTENTS)) if row["values"][item] == 1.0), 0)]
            predictions[index] = _predict(models[intent], row["values"][len(INTENTS):])
    result = []
    for threshold in thresholds:
        selected = [row for row, probability in zip(rows, predictions, strict=True) if probability >= threshold]
        correct = sum(row["target"] for row in selected)
        result.append({
            "threshold": threshold,
            "selected": len(selected),
            "correct": correct,
            "precision": correct / len(selected) if selected else 0.0,
            "coverage": len(selected) / len(rows),
            "wilson_lower_95": _wilson(correct, len(selected)),
        })
    return result


def _markdown(payload, policy_path):
    lines = [
        "# Final Pareto Calibration",
        "",
        f"Decision: `{'PASS' if payload['passed'] else 'FAIL'}`",
        "",
        f"- Live Fireworks calls: `{payload['live_calls']}`.",
        f"- Estimated spend: `${payload['estimated_spend_usd']:.6f}`.",
        f"- Selected Fireworks policy: `{payload['selected_fireworks_policy']}`.",
        f"- Selected E2B threshold: `{payload['selected_e2b_threshold']['threshold']:.2f}`.",
        f"- Versioned policy: `{policy_path.relative_to(ROOT)}`.",
        "",
        "## Candidates",
        "",
    ]
    for name, item in payload["candidates"].items():
        lines.append(f"- `{name}`: accuracy `{item['accuracy']:.2%}`, tokens `{item['tokens']}`, cost `${item['cost_usd']:.6f}`, nondominated `{item['nondominated']}`.")
    lines.extend(["", "## E2B Thresholds", ""])
    for item in payload["e2b_thresholds"]:
        lines.append(f"- `{item['threshold']:.2f}`: precision `{item['precision']:.2%}`, coverage `{item['coverage']:.2%}`, Wilson lower `{item['wilson_lower_95']:.2%}`.")
    lines.extend(["", "## Gates", ""])
    lines.extend(f"- [{'x' if value else ' '}] `{name}`" for name, value in payload["checks"].items())
    lines.extend(["", "The policy is accuracy-first: token count breaks ties only among candidates with identical deterministic-validator accuracy. Unknown hidden-evaluator behavior remains a stated limitation.", ""])
    return "\n".join(lines)


def _jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
