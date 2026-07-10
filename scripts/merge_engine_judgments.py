#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "engine-outcome-judgment-v1"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Atomically merge independently generated judgment JSONL files.")
    root.add_argument("--input", action="append", type=Path, required=True)
    root.add_argument("--output", type=Path, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    result = merge_judgments(args.input, args.output)
    print(json.dumps(result, sort_keys=True))
    return 0


def merge_judgments(inputs: Sequence[Path], output: Path) -> dict[str, Any]:
    if len(inputs) < 2:
        raise ValueError("At least two judgment inputs are required.")
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    counts: dict[str, int] = {}
    for path in inputs:
        rows = _jsonl(path)
        counts[str(path)] = len(rows)
        for row in rows:
            _validate_row(row, path)
            key = (str(row["candidate_id"]), str(row["judge_model"]))
            if key in merged:
                raise ValueError(f"Duplicate judgment key {key!r} across merge inputs.")
            merged[key] = row
    ordered = [merged[key] for key in sorted(merged)]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(str(output) + ".merge-partial")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in ordered:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
    temporary.replace(output)
    return {
        "schema_version": "engine-outcome-judgment-merge-v1",
        "inputs": counts,
        "output": str(output),
        "rows": len(ordered),
        "unique_candidate_judge_pairs": len(merged),
    }


def _validate_row(row: Mapping[str, Any], path: Path) -> None:
    if row.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"{path} contains an incompatible judgment schema.")
    for field in ("candidate_id", "judge_model", "verdict", "format_valid", "provenance"):
        if field not in row:
            raise ValueError(f"{path} judgment is missing {field!r}.")


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must be a JSON object.")
        rows.append(row)
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
