#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable, Mapping, Sequence

SCHEMA = "e2b-contract-judge-consensus-v1"
VERDICTS = {"correct", "incorrect"}
SOURCE_VERDICTS = VERDICTS | {"uncertain"}


def _rows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            raise ValueError(f"missing input: {path}")
        result.extend(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    return result


def _candidate_id(row: Mapping[str, Any]) -> str:
    value = row.get("candidate_id", row.get("id"))
    if not isinstance(value, str) or not value:
        raise ValueError("row is missing candidate_id/id")
    return value


def _candidate_index(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate_id = _candidate_id(row)
        if candidate_id in result:
            raise ValueError(f"duplicate candidate: {candidate_id}")
        result[candidate_id] = dict(row)
    return result


def _judge_index(rows: Sequence[Mapping[str, Any]], role: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate_id = _candidate_id(row)
        verdict = str(row.get("verdict", ""))
        if verdict not in SOURCE_VERDICTS:
            raise ValueError(f"invalid {role} verdict for {candidate_id}: {verdict!r}")
        normalized = "incorrect" if verdict == "uncertain" else verdict
        normalized_row = dict(row)
        normalized_row["source_verdict"] = verdict
        normalized_row["verdict"] = normalized
        if candidate_id in result:
            prior = result[candidate_id]
            same_vote = prior["verdict"] == normalized and prior.get("judge_model") == row.get("judge_model")
            if not same_vote:
                raise ValueError(f"conflicting {role} judgments: {candidate_id}")
            continue
        result[candidate_id] = normalized_row
    return result


def _vote(role: str, row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "role": role,
        "judge_model": str(row.get("judge_model") or row.get("judge_provider") or role),
        "verdict": str(row["verdict"]),
    }


def merge(
    candidates: Sequence[Mapping[str, Any]],
    glm_rows: Sequence[Mapping[str, Any]],
    assigned_rows: Sequence[Mapping[str, Any]],
    third_rows: Sequence[Mapping[str, Any]] = (),
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidate_by_id = _candidate_index(candidates)
    glm = _judge_index(glm_rows, "glm")
    assigned = _judge_index(assigned_rows, "assigned")
    third = _judge_index(third_rows, "third")
    unknown = (set(glm) | set(assigned) | set(third)) - set(candidate_by_id)
    if unknown:
        raise ValueError(f"judgments reference unknown candidates: {len(unknown)}")

    audit: Counter[str] = Counter()
    output: list[dict[str, Any]] = []
    for candidate_id in sorted(candidate_by_id):
        candidate = candidate_by_id[candidate_id]
        mechanical = candidate.get("mechanical") or {}
        hard = bool(mechanical.get("hard"))
        mechanical_verdict = str(mechanical.get("verdict", "uncertain"))
        votes: list[dict[str, Any]] = []
        if hard:
            if mechanical_verdict not in VERDICTS:
                raise ValueError(f"hard mechanical verdict is not binary: {candidate_id}")
            verdict = mechanical_verdict
            source = "mechanical"
            judge_model = "consensus:mechanical"
            audit["mechanical_authoritative"] += 1
        else:
            glm_row, assigned_row = glm.get(candidate_id), assigned.get(candidate_id)
            if glm_row is None or assigned_row is None:
                verdict = "incorrect"
                source = "conservative_missing_primary"
                judge_model = "consensus:missing_primary->incorrect"
                audit["semantic_missing_primary"] += 1
                if glm_row is not None:
                    votes.append(_vote("glm", glm_row))
                if assigned_row is not None:
                    votes.append(_vote("assigned", assigned_row))
            else:
                votes = [_vote("glm", glm_row), _vote("assigned", assigned_row)]
                if glm_row["verdict"] == assigned_row["verdict"]:
                    verdict = str(glm_row["verdict"])
                    source = "judge_consensus"
                    judge_model = "consensus:glm+assigned"
                    audit["semantic_pair_agreement"] += 1
                else:
                    audit["semantic_pair_disagreement"] += 1
                    third_row = third.get(candidate_id)
                    if third_row is None:
                        verdict = "incorrect"
                        source = "conservative_disagreement"
                        judge_model = "consensus:disagreement->incorrect"
                        audit["semantic_disagreement_without_third"] += 1
                    else:
                        votes.append(_vote("third", third_row))
                        counts = Counter(row["verdict"] for row in votes)
                        verdict = counts.most_common(1)[0][0]
                        source = "third_judge_majority"
                        judge_model = "consensus:glm+assigned+third"
                        audit["semantic_disagreement_resolved_by_third"] += 1

        audit[f"final_{verdict}"] += 1
        audit[f"evidence_{source}"] += 1
        output.append(
            {
                "schema_version": SCHEMA,
                "candidate_id": candidate_id,
                "task_id": candidate.get("task_id"),
                "verdict": verdict,
                "judge_model": judge_model,
                "evidence_source": source,
                "mechanical_verdict": mechanical_verdict,
                "mechanical_hard": hard,
                "votes": votes,
            }
        )

    audit.update(
        {
            "rows": len(output),
            "glm_input_rows": len(glm),
            "assigned_input_rows": len(assigned),
            "third_input_rows": len(third),
        }
    )
    summary = {
        "schema_version": SCHEMA,
        "policy": {
            "mechanical": "authoritative",
            "semantic_pair": "GLM plus assigned Codex/Agy",
            "pair_agreement": "agreed binary verdict",
            "pair_disagreement": "third-judge majority when available, otherwise incorrect",
            "missing_primary": "incorrect",
        },
        "counts": dict(sorted(audit.items())),
    }
    return output, summary


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge mechanical and multi-judge E2B verdicts.")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--glm", type=Path, nargs="+", required=True)
    parser.add_argument("--assigned", type=Path, nargs="+", required=True)
    parser.add_argument("--third", type=Path, nargs="*", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args(argv)
    merged, audit = merge(
        _rows([args.candidates]),
        _rows(args.glm),
        _rows(args.assigned),
        _rows(args.third),
    )
    _atomic_text(
        args.output,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in merged),
    )
    _atomic_text(args.audit, json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(json.dumps(audit["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
