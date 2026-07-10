#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


SCORE_NAMES = (
    "deterministic_fit",
    "format_complexity",
    "generation_demand",
    "knowledge_uncertainty",
    "reasoning_demand",
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Analyze marginal E2B accuracy across token ceilings.")
    root.add_argument("--stage", action="append", required=True, metavar="TOKENS:CANDIDATES:CONSENSUS")
    root.add_argument("--json-output", type=Path, required=True)
    root.add_argument("--markdown-output", type=Path, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    stages = [_parse_stage(value) for value in args.stage]
    report = analyze(stages)
    _write_json(args.json_output, report)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


def analyze(stages: Sequence[tuple[int, Path, Path]]) -> dict[str, Any]:
    if len(stages) < 2:
        raise ValueError("At least two token stages are required.")
    ordered = sorted(stages, key=lambda item: item[0])
    limits = [item[0] for item in ordered]
    if len(set(limits)) != len(limits):
        raise ValueError("Token stages must be unique.")

    candidates: dict[int, dict[str, dict[str, Any]]] = {}
    consensus: dict[int, dict[str, dict[str, Any]]] = {}
    stage_summaries: list[dict[str, Any]] = []
    for limit, candidate_path, consensus_path in ordered:
        candidate_index = _index(_jsonl(candidate_path), "task_id")
        consensus_index = _index(_jsonl(consensus_path), "task_id")
        if set(candidate_index) != set(consensus_index):
            raise ValueError(f"Candidate and consensus task ids differ at stage {limit}.")
        candidates[limit] = candidate_index
        consensus[limit] = consensus_index
        stage_summaries.append(_stage_summary(limit, list(consensus_index.values())))

    transitions: list[dict[str, Any]] = []
    task_transitions: list[dict[str, Any]] = []
    for previous, current in zip(limits, limits[1:]):
        current_ids = set(candidates[current])
        if not current_ids.issubset(candidates[previous]):
            raise ValueError(f"Stage {current} contains tasks absent from stage {previous}.")
        rows = [
            _transition_row(
                previous,
                current,
                candidates[previous][task_id],
                candidates[current][task_id],
                consensus[current][task_id],
            )
            for task_id in sorted(current_ids)
        ]
        task_transitions.extend(rows)
        transitions.append(_transition_summary(previous, current, rows))

    genuine = sum(row["genuine_recoveries"] for row in transitions)
    flips = sum(row["judge_flips_without_output_change"] for row in transitions)
    summary = {
        "token_limits": limits,
        "initial_tasks": len(candidates[limits[0]]),
        "initial_unanimous_correct": stage_summaries[0]["outcomes"].get("correct", 0),
        "genuine_incremental_recoveries": genuine,
        "judge_flips_without_output_change": flips,
        "evidence_policy": "Only prefix-growing answers newly judged correct count as token-budget recovery.",
    }
    return {
        "schema_version": "e2b-token-ladder-analysis-v1",
        "summary": summary,
        "stages": stage_summaries,
        "transitions": transitions,
        "task_transitions": task_transitions,
    }


def _transition_row(
    previous_limit: int,
    current_limit: int,
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
    judgment: Mapping[str, Any],
) -> dict[str, Any]:
    previous_answer = str(previous.get("answer") or "")
    current_answer = str(current.get("answer") or "")
    if previous_answer == current_answer:
        answer_relation = "identical"
    elif current_answer.startswith(previous_answer):
        answer_relation = "prefix_growth"
    else:
        answer_relation = "changed_non_prefix"
    outcome = str(judgment["outcome"])
    if outcome == "correct" and answer_relation == "prefix_growth":
        classification = "genuine_recovery"
    elif outcome == "correct" and answer_relation == "identical":
        classification = "judge_flip_without_output_change"
    elif outcome == "correct":
        classification = "changed_answer_recovery"
    elif outcome == "disagree":
        classification = "disagreement"
    else:
        classification = "still_failed"
    return {
        "task_id": str(current["task_id"]),
        "from_tokens": previous_limit,
        "to_tokens": current_limit,
        "intent": str(judgment["intent"]),
        "scores": dict(judgment["scores"]),
        "outcome": outcome,
        "answer_relation": answer_relation,
        "classification": classification,
        "previous_answer_chars": len(previous_answer),
        "current_answer_chars": len(current_answer),
        "latency_ms": float(judgment["latency_ms"]),
    }


def _stage_summary(limit: int, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    outcomes = Counter(str(row["outcome"]) for row in rows)
    latencies = [float(row["latency_ms"]) for row in rows]
    return {
        "tokens": limit,
        "tasks": len(rows),
        "outcomes": dict(sorted(outcomes.items())),
        "latency_ms": {
            "total": round(sum(latencies), 3),
            "mean": round(statistics.mean(latencies), 3),
            "median": round(statistics.median(latencies), 3),
        },
        "score_means_by_outcome": {
            outcome: _score_means([row for row in rows if row["outcome"] == outcome])
            for outcome in sorted(outcomes)
        },
    }


def _transition_summary(previous: int, current: int, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    classes = Counter(str(row["classification"]) for row in rows)
    relations = Counter(str(row["answer_relation"]) for row in rows)
    genuine = [row for row in rows if row["classification"] == "genuine_recovery"]
    by_intent: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        by_intent[str(row["intent"])][str(row["classification"])] += 1
    return {
        "from_tokens": previous,
        "to_tokens": current,
        "retried_tasks": len(rows),
        "classifications": dict(sorted(classes.items())),
        "answer_relations": dict(sorted(relations.items())),
        "genuine_recoveries": len(genuine),
        "judge_flips_without_output_change": classes.get("judge_flip_without_output_change", 0),
        "genuine_recovery_rate": round(len(genuine) / len(rows), 6) if rows else 0.0,
        "genuine_recovery_score_means": _score_means(genuine),
        "genuine_recoveries_by_intent": dict(sorted(Counter(row["intent"] for row in genuine).items())),
        "classifications_by_intent": {
            intent: dict(sorted(counts.items())) for intent, counts in sorted(by_intent.items())
        },
    }


def _score_means(rows: Sequence[Mapping[str, Any]]) -> dict[str, float | None]:
    if not rows:
        return {name: None for name in SCORE_NAMES}
    return {
        name: round(statistics.mean(float(row["scores"][name]) for row in rows), 3)
        for name in SCORE_NAMES
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Gemma E2B Token-Ceiling Frontier",
        "",
        "## Executive Result",
        "",
        f"- initial tasks: `{summary['initial_tasks']}`;",
        f"- initial unanimous-correct at {summary['token_limits'][0]} tokens: `{summary['initial_unanimous_correct']}`;",
        f"- genuine incremental recoveries: `{summary['genuine_incremental_recoveries']}`;",
        f"- judge flips without output change: `{summary['judge_flips_without_output_change']}`;",
        f"- policy: {summary['evidence_policy']}",
        "",
        "## Marginal Frontier",
        "",
        "| Transition | Retried | Genuine recovery | Judge-only flip | Recovery rate | Recovery intents |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in report["transitions"]:
        intents = ", ".join(f"{key}: {value}" for key, value in row["genuine_recoveries_by_intent"].items()) or "none"
        lines.append(
            f"| {row['from_tokens']} -> {row['to_tokens']} | {row['retried_tasks']} | "
            f"{row['genuine_recoveries']} | {row['judge_flips_without_output_change']} | "
            f"{100 * row['genuine_recovery_rate']:.2f}% | {intents} |"
        )
    lines.extend([
        "",
        "## Parameter Means For Genuine Recoveries",
        "",
        "| Transition | Deterministic | Format | Generation | Knowledge | Reasoning |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in report["transitions"]:
        scores = row["genuine_recovery_score_means"]
        lines.append(
            f"| {row['from_tokens']} -> {row['to_tokens']} | {scores['deterministic_fit']} | "
            f"{scores['format_complexity']} | {scores['generation_demand']} | "
            f"{scores['knowledge_uncertainty']} | {scores['reasoning_demand']} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "A higher ceiling is useful only when the prior answer is a strict prefix of the new answer and the new answer becomes unanimously correct. Identical answers with changed judgments are evaluator variance, not evidence that more decode budget helped.",
        "",
        "Do not infer a production routing threshold from these descriptive means alone. Fit and validate the policy on mutation-lineage-separated data, and include latency plus the ten-minute batch deadline in the objective.",
        "",
    ])
    return "\n".join(lines)


def _parse_stage(value: str) -> tuple[int, Path, Path]:
    parts = value.split(":", 2)
    if len(parts) != 3:
        raise ValueError("Each --stage must be TOKENS:CANDIDATES:CONSENSUS.")
    return int(parts[0]), Path(parts[1]), Path(parts[2])


def _index(rows: Sequence[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = str(row.get(key) or "")
        if not value or value in result:
            raise ValueError(f"Rows require unique non-empty {key} values.")
        result[value] = row
    return result


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
