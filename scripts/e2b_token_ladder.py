#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


OUTCOMES = {"correct", "incorrect", "disagree"}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Build conservative E2B token-ladder retry sets.")
    root.add_argument("--candidates", type=Path, required=True)
    root.add_argument("--judgments", type=Path, required=True)
    root.add_argument("--tasks", type=Path, required=True)
    root.add_argument("--judge-model", action="append", required=True)
    root.add_argument("--consensus-output", type=Path, required=True)
    root.add_argument("--retry-tasks-output", type=Path, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    result = build_retry_set(
        candidates_path=args.candidates,
        judgments_path=args.judgments,
        tasks_path=args.tasks,
        judge_models=tuple(args.judge_model),
        consensus_output=args.consensus_output,
        retry_tasks_output=args.retry_tasks_output,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


def build_retry_set(
    *,
    candidates_path: Path,
    judgments_path: Path,
    tasks_path: Path,
    judge_models: tuple[str, ...],
    consensus_output: Path,
    retry_tasks_output: Path,
) -> dict[str, Any]:
    if len(judge_models) < 2 or len(set(judge_models)) != len(judge_models):
        raise ValueError("At least two distinct judge models are required.")
    candidates = _jsonl(candidates_path)
    judgments = _judgment_index(_jsonl(judgments_path))
    consensus: list[dict[str, Any]] = []
    retry_task_ids: set[str] = set()
    counts = {outcome: 0 for outcome in sorted(OUTCOMES)}
    for candidate in candidates:
        _validate_candidate(candidate)
        selected = []
        for model in judge_models:
            judgment = judgments.get((str(candidate["id"]), model))
            if judgment is None:
                raise ValueError(f"Missing judgment for candidate {candidate['id']!r} and model {model!r}.")
            selected.append(judgment)
        verdicts = [str(row["verdict"]) for row in selected]
        outcome = "correct" if all(value == "correct" for value in verdicts) else (
            "incorrect" if all(value == "incorrect" for value in verdicts) else "disagree"
        )
        counts[outcome] += 1
        if outcome != "correct":
            retry_task_ids.add(str(candidate["task_id"]))
        consensus.append(
            {
                "candidate_id": candidate["id"],
                "task_id": candidate["task_id"],
                "generation_limit_tokens": candidate["generation_limit_tokens"],
                "outcome": outcome,
                "intent": candidate["functiongemma_assessment"]["intent"],
                "scores": candidate["functiongemma_assessment"]["scores"],
                "latency_ms": candidate["latency_ms"],
                "answer_chars": len(candidate["answer"]),
                "judge_verdicts": {model: row["verdict"] for model, row in zip(judge_models, selected, strict=True)},
            }
        )
    tasks = _jsonl(tasks_path)
    retry_tasks = [row for row in tasks if str(row.get("id")) in retry_task_ids]
    if len(retry_tasks) != len(retry_task_ids):
        raise ValueError("Retry task source is missing one or more task ids.")
    _write_jsonl(consensus_output, consensus)
    _write_jsonl(retry_tasks_output, retry_tasks)
    return {
        "candidates": len(candidates),
        "correct": counts["correct"],
        "incorrect": counts["incorrect"],
        "disagree": counts["disagree"],
        "retry_tasks": len(retry_tasks),
        "generation_limit_tokens": sorted({row["generation_limit_tokens"] for row in consensus}),
    }


def _judgment_index(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], Mapping[str, Any]]:
    result: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in rows:
        key = (str(row.get("candidate_id") or ""), str(row.get("judge_model") or ""))
        if not all(key):
            continue
        if key in result:
            raise ValueError(f"Duplicate judgment for {key!r}.")
        result[key] = row
    return result


def _validate_candidate(row: Mapping[str, Any]) -> None:
    required = {"id", "task_id", "generation_limit_tokens", "functiongemma_assessment", "answer", "latency_ms"}
    if not required.issubset(row):
        raise ValueError("Token-ladder candidates require the v2 observation contract.")
    if row.get("failure"):
        raise ValueError("Failed candidate observations require separate runtime adjudication.")


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_number} must be an object.")
        rows.append(payload)
    return rows


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
