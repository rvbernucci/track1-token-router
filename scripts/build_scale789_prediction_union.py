#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_INPUTS = (
    Path("reports/generated/amd-pod-e2b-regression-2000/functiongemma-predictions.jsonl"),
    Path("reports/generated/e2b-expansion-v1/functiongemma.jsonl"),
    Path("reports/generated/e2b-boundary-v1/predictions.jsonl"),
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize production scale789 FunctionGemma predictions.")
    parser.add_argument("--input", action="append", type=Path, dest="inputs")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = prediction_union(args.inputs or DEFAULT_INPUTS)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"rows": len(rows), "output": str(args.output)}, sort_keys=True))
    return 0


def prediction_union(paths: Sequence[Path]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for path in paths:
        for raw in _rows(path):
            task_id = str(raw.get("id") or raw.get("task_id") or "").strip()
            if not task_id:
                raise ValueError(f"Prediction in {path} has no task ID.")
            prediction = _assessment(raw)
            if prediction is None:
                continue
            normalized = {"id": task_id, "prediction": prediction, "source_path": str(path)}
            previous = by_id.get(task_id)
            if previous is not None and previous["prediction"] != prediction:
                raise ValueError(f"Conflicting production predictions for {task_id}.")
            by_id[task_id] = normalized
    if not by_id:
        raise ValueError("No valid production predictions were found.")
    return [by_id[task_id] for task_id in sorted(by_id)]


def _assessment(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for candidate in (
        row.get("prediction"),
        row.get("assessment"),
        row.get("assessment", {}).get("raw_assessment") if isinstance(row.get("assessment"), Mapping) else None,
        row.get("assessment", {}).get("assessment") if isinstance(row.get("assessment"), Mapping) else None,
    ):
        if not isinstance(candidate, Mapping):
            continue
        if isinstance(candidate.get("intent"), str) and isinstance(candidate.get("scores"), Mapping):
            return {"intent": candidate["intent"], "scores": dict(candidate["scores"])}
    return None


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
