#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Transfer judgments between byte-identical answer observations.")
    root.add_argument("--source-candidates", type=Path, required=True)
    root.add_argument("--target-candidates", type=Path, required=True)
    root.add_argument("--source-judgments", type=Path, required=True)
    root.add_argument("--output", type=Path, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    result = transfer(
        source_candidates=args.source_candidates,
        target_candidates=args.target_candidates,
        source_judgments=args.source_judgments,
        output=args.output,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


def transfer(
    *,
    source_candidates: Path,
    target_candidates: Path,
    source_judgments: Path,
    output: Path,
) -> dict[str, Any]:
    sources = _index(_jsonl(source_candidates), "task_id")
    targets = _index(_jsonl(target_candidates), "task_id")
    if set(sources) != set(targets):
        raise ValueError("Source and target candidate sets must contain identical task ids.")
    source_by_id = {str(row["id"]): row for row in sources.values()}
    target_by_source: dict[str, Mapping[str, Any]] = {}
    for task_id, source in sources.items():
        target = targets[task_id]
        _require_equivalent(source, target)
        target_by_source[str(source["id"])] = target

    transferred: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for judgment in _jsonl(source_judgments):
        source_id = str(judgment.get("candidate_id") or "")
        target = target_by_source.get(source_id)
        if target is None:
            continue
        judge = str(judgment.get("judge_model") or "")
        key = (str(target["id"]), judge)
        if not judge or key in seen:
            raise ValueError("Transferred judgments require unique target candidate and judge pairs.")
        seen.add(key)
        answer = str(target["answer"])
        transferred.append(
            {
                **judgment,
                "schema_version": "engine-outcome-judgment-transfer-v1",
                "candidate_id": target["id"],
                "source_candidate_id": source_id,
                "transfer": {
                    "reason": "byte_identical_answer_observation",
                    "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
                    "source_runtime_id": source.get("runtime_id"),
                    "target_runtime_id": target.get("runtime_id"),
                },
            }
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in transferred),
        encoding="utf-8",
    )
    return {"tasks": len(targets), "judgments_transferred": len(transferred), "output": str(output)}


def _require_equivalent(source: Mapping[str, Any], target: Mapping[str, Any]) -> None:
    fields = ("task_id", "model_id", "generation_limit_tokens", "answer")
    if any(source.get(field) != target.get(field) for field in fields):
        raise ValueError(f"Candidate observations are not equivalent for task {source.get('task_id')!r}.")
    if source.get("failure") or target.get("failure") or source.get("refusal") or target.get("refusal"):
        raise ValueError("Only successful answered observations may inherit judgments.")


def _index(rows: Sequence[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = str(row.get(field) or "")
        if not value or value in result:
            raise ValueError(f"Candidates require unique non-empty {field} values.")
        result[value] = row
    return result


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
