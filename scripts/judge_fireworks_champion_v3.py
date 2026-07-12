#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MODELS = ("accounts/fireworks/models/kimi-k2p7-code", "accounts/fireworks/models/minimax-m3")


def _rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    temporary.replace(path)


def _references() -> dict[str, dict[str, Any]]:
    paths = (
        "evals/e2b-expansion-v1/references/train.jsonl",
        "evals/e2b-expansion-v1/references/calibration.jsonl",
        "evals/e2b-expansion-v1/sealed/references/final_holdout.jsonl",
        "evals/e2b-regression-v2/references/train.jsonl",
        "evals/e2b-regression-v2/references/validation.jsonl",
        "evals/e2b-regression-v2/sealed/final_holdout.jsonl",
    )
    result: dict[str, dict[str, Any]] = {}
    for relative in paths:
        for row in _rows(ROOT / relative):
            if row["task_id"] in result:
                raise ValueError(f"duplicate reference {row['task_id']}")
            result[row["task_id"]] = row
    return result


def _normalize(value: str) -> str:
    return " ".join(value.strip().casefold().split()).rstrip(".")


def deterministic_verdict(task: dict[str, Any], response: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    if not response.get("ok") or not str(response.get("answer", "")).strip():
        return {"verdict": "incorrect", "hard": True, "reason": "missing_response"}
    answer = str(response["answer"]).strip()
    expected = str(reference.get("reference_answer", "")).strip()
    mode = reference.get("answer_mode")
    evidence = task.get("evidence_mode")
    if mode == "exact" or (evidence == "mechanical" and task.get("output_shape") in {"number", "label", "short_text"}):
        return {"verdict": "correct" if _normalize(answer) == _normalize(expected) else "incorrect", "hard": True, "reason": "normalized_exact"}
    if task.get("output_shape") == "json":
        try:
            json.loads(answer)
        except (TypeError, json.JSONDecodeError):
            return {"verdict": "incorrect", "hard": True, "reason": "invalid_json"}
    if response.get("finish_reason") == "length":
        return {"verdict": "incorrect", "hard": True, "reason": "truncated"}
    return {"verdict": "uncertain", "hard": False, "reason": "semantic_or_complex_contract"}


def wilson(successes: int, total: int, z: float = 1.96) -> float:
    if total == 0:
        return 0.0
    p = successes / total
    denominator = 1 + z * z / total
    return (p + z * z / (2 * total) - z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)) / denominator


def _mcnemar_exact(left_only: int, right_only: int) -> float:
    discordant = left_only + right_only
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, index) for index in range(min(left_only, right_only) + 1)) / (2 ** discordant)
    return min(1.0, 2 * tail)


def _model_metrics(rows: list[dict[str, Any]], by_pair: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    successes = sum(bool(row["correct"]) for row in rows)
    usage_rows = [by_pair[(row["task_id"], row["model"])] for row in rows]
    return {
        "judged": len(rows), "correct": successes,
        "accuracy": successes / len(rows) if rows else None,
        "wilson_lower_95": wilson(successes, len(rows)),
        "tokens": sum(int((item.get("usage") or {}).get("total", 0)) for item in usage_rows),
        "prompt_tokens": sum(int((item.get("usage") or {}).get("prompt", 0)) for item in usage_rows),
        "completion_tokens": sum(int((item.get("usage") or {}).get("completion", 0)) for item in usage_rows),
        "median_latency_ms": statistics.median(item["latency_ms"] for item in usage_rows) if usage_rows else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Mechanical-first blind adjudication for champion v3")
    parser.add_argument("--tasks", type=Path, default=Path("evals/fireworks-champion-v3/tasks.jsonl"))
    parser.add_argument("--responses", type=Path, default=Path("reports/generated/fireworks-champion-v3/responses.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/generated/fireworks-champion-v3"))
    parser.add_argument("--codex-judgments", type=Path)
    parser.add_argument("--seed", type=int, default=76076)
    args = parser.parse_args()
    resolve = lambda value: value if value.is_absolute() else ROOT / value
    tasks = {row["task_id"]: row for row in _rows(resolve(args.tasks))}
    references = _references()
    responses = _rows(resolve(args.responses))
    by_pair = {(row["task_id"], row["model"]): row for row in responses}
    output = resolve(args.output_dir)
    rng = random.Random(args.seed)
    mechanics: list[dict[str, Any]] = []
    queue: list[dict[str, Any]] = []
    blind_key: dict[str, dict[str, str]] = {}
    for task_id in sorted(tasks):
        task = tasks[task_id]
        reference = references.get(task_id)
        if reference is None:
            raise ValueError(f"missing reference {task_id}")
        candidates = []
        for model in MODELS:
            response = by_pair.get((task_id, model))
            if response is None:
                continue
            verdict = deterministic_verdict(task, response, reference)
            mechanics.append({"task_id": task_id, "model": model, **verdict})
            candidates.append((model, response, verdict))
        if len(candidates) != 2 or all(item[2]["hard"] for item in candidates):
            continue
        rng.shuffle(candidates)
        blind_id = hashlib.sha256(f"{args.seed}:{task_id}".encode()).hexdigest()[:20]
        queue.append({
            "schema_version": "fireworks-champion-v3-blind-judge-v1", "blind_id": blind_id,
            "task_id": task_id, "split": task["split"], "category": task["category"],
            "prompt": task["prompt"], "reference_answer": reference.get("reference_answer"),
            "reference_rubric": reference.get("reference_rubric"),
            "candidate_a": candidates[0][1]["answer"], "candidate_b": candidates[1][1]["answer"],
            "instruction": "Judge each candidate independently. Return valid_a, valid_b, winner (a|b|tie|neither), and a concise reason. Ignore model style and identity.",
        })
        blind_key[blind_id] = {"candidate_a": candidates[0][0], "candidate_b": candidates[1][0]}
    _write(output / "mechanical-verdicts.jsonl", mechanics)
    _write(output / "codex-blind-queue.jsonl", queue)
    (output / "blind-key.json").write_text(json.dumps(blind_key, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    judgments = _rows(resolve(args.codex_judgments)) if args.codex_judgments else []
    judged = {row["blind_id"]: row for row in judgments}
    final: list[dict[str, Any]] = []
    mechanics_by_pair = {(row["task_id"], row["model"]): row for row in mechanics}
    blind_by_task = {row["task_id"]: row for row in queue}
    for pair, response in sorted(by_pair.items()):
        task_id, model = pair
        mechanical = mechanics_by_pair[pair]
        correct = mechanical["verdict"] == "correct" if mechanical["hard"] else None
        evidence = "mechanical" if mechanical["hard"] else "pending_codex"
        blind = blind_by_task.get(task_id)
        if correct is None and blind and blind["blind_id"] in judged:
            judgment = judged[blind["blind_id"]]
            side = "a" if blind_key[blind["blind_id"]]["candidate_a"] == model else "b"
            correct = bool(judgment[f"valid_{side}"])
            evidence = "blind_codex"
        final.append({"task_id": task_id, "model": model, "correct": correct, "evidence": evidence})
    _write(output / "final-verdicts.jsonl", final)

    completed = [row for row in final if row["correct"] is not None]
    metrics: dict[str, Any] = {"rows_expected": len(tasks) * 2, "responses": len(responses), "judge_queue": len(queue), "judge_completed": len(judged)}
    groups: dict[str, Any] = {}
    for model in MODELS:
        rows = [row for row in completed if row["model"] == model]
        groups[model] = _model_metrics(rows, by_pair)
    metrics["models"] = groups
    category_metrics: dict[str, Any] = {}
    recommendation: dict[str, Any] = {"objective": "maximize_accuracy_then_minimize_tokens", "by_category": {}, "statistically_supported_overrides": {}}
    for category in sorted({task["category"] for task in tasks.values()}):
        category_task_ids = {task_id for task_id, task in tasks.items() if task["category"] == category}
        category_metrics[category] = {}
        candidates = []
        for model in MODELS:
            rows = [row for row in completed if row["model"] == model and row["task_id"] in category_task_ids]
            category_metrics[category][model] = _model_metrics(rows, by_pair)
            model_metrics = category_metrics[category][model]
            candidates.append((model_metrics["accuracy"], -model_metrics["tokens"], model))
        _, _, champion = max(candidates)
        other = next(model for model in MODELS if model != champion)
        recommendation["by_category"][category] = {
            "preferred_model": champion,
            "accuracy_delta_vs_other": category_metrics[category][champion]["accuracy"] - category_metrics[category][other]["accuracy"],
            "token_delta_vs_other": category_metrics[category][champion]["tokens"] - category_metrics[category][other]["tokens"],
            "promotion_status": "candidate_only_requires_sealed_policy_review",
        }
        category_ids = sorted(category_task_ids)
        final_lookup = {(row["task_id"], row["model"]): bool(row["correct"]) for row in completed}
        kimi_only = sum(final_lookup[(task_id, MODELS[0])] and not final_lookup[(task_id, MODELS[1])] for task_id in category_ids)
        minimax_only = sum(final_lookup[(task_id, MODELS[1])] and not final_lookup[(task_id, MODELS[0])] for task_id in category_ids)
        paired_p = _mcnemar_exact(kimi_only, minimax_only)
        recommendation["by_category"][category]["paired"] = {
            "kimi_only_correct": kimi_only, "minimax_only_correct": minimax_only,
            "discordant": kimi_only + minimax_only, "mcnemar_exact_p": paired_p,
        }
        if paired_p < 0.05 and kimi_only != minimax_only:
            recommendation["statistically_supported_overrides"][category] = MODELS[0] if kimi_only > minimax_only else MODELS[1]
    metrics["by_category"] = category_metrics
    recommendation["overall"] = max(
        MODELS,
        key=lambda model: (groups[model]["accuracy"], -groups[model]["tokens"]),
    )
    metrics["recommendation"] = recommendation
    metrics["complete"] = len(final) == len(tasks) * 2 and all(row["correct"] is not None for row in final)
    (output / "summary.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "policy-recommendation.json").write_text(json.dumps(recommendation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
