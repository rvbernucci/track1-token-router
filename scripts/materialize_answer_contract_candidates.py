#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.orchestration.final_validator import apply_answer_contract


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize candidates after the Answer Contract Engine.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--changed-output", type=Path)
    args = parser.parse_args(argv)

    result = materialize(_absolute(args.candidates))
    _write_jsonl(_absolute(args.output), result["rows"])
    if args.changed_output:
        _write_jsonl(_absolute(args.changed_output), result["changed_rows"])
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


def materialize(candidates_path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    changed_rows: list[dict[str, Any]] = []
    valid = 0
    for source in _jsonl(candidates_path):
        application = apply_answer_contract(
            TaskEnvelope(id=str(source["task_id"]), input_text=str(source["task_text"])),
            str(source.get("answer") or ""),
        )
        row = dict(source)
        row["answer_before_contract"] = str(source.get("answer") or "")
        row["answer"] = application.answer if application.valid else str(source.get("answer") or "").strip()
        row["answer_contract"] = application.to_dict()
        row["answer_contract_changed"] = application.changed
        row["answer_contract_valid"] = application.valid
        rows.append(row)
        valid += int(application.valid)
        if application.changed:
            changed_rows.append(row)
    return {
        "summary": {
            "rows": len(rows),
            "changed": len(changed_rows),
            "unchanged": len(rows) - len(changed_rows),
            "contract_valid": valid,
            "contract_invalid": len(rows) - valid,
        },
        "rows": rows,
        "changed_rows": changed_rows,
    }


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
