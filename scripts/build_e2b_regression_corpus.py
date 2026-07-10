#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from router.functiongemma.tooling import DEVELOPER_INSTRUCTION


INTENTS = (
    "factual_qa",
    "math_reasoning",
    "sentiment",
    "summarization",
    "ner",
    "code_debugging",
    "logic_puzzle",
    "code_generation",
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Build a balanced E2B regression corpus from validated proposals.")
    root.add_argument("--proposals", action="append", type=Path, required=True)
    root.add_argument("--per-intent", type=int, default=250)
    root.add_argument("--output", type=Path, required=True)
    root.add_argument("--manifest", type=Path, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    report = build_corpus(
        proposal_paths=args.proposals,
        per_intent=args.per_intent,
        output=args.output,
        manifest=args.manifest,
    )
    print(json.dumps(report, sort_keys=True))
    return 0


def build_corpus(
    *,
    proposal_paths: Sequence[Path],
    per_intent: int,
    output: Path,
    manifest: Path,
) -> dict[str, Any]:
    if per_intent < 1:
        raise ValueError("per_intent must be positive.")
    deduped: dict[str, dict[str, Any]] = {}
    for path in proposal_paths:
        for row in _jsonl(path):
            _validate(row)
            content_hash = str(row["content_sha256"])
            current = deduped.get(content_hash)
            if current is None or str(row["id"]) < str(current["id"]):
                deduped[content_hash] = row
    by_intent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in deduped.values():
        by_intent[str(row["assessment"]["intent"])].append(row)
    missing = {intent: per_intent - len(by_intent[intent]) for intent in INTENTS if len(by_intent[intent]) < per_intent}
    if missing:
        raise ValueError(f"Not enough unique proposals per intent: {missing!r}.")
    selected: list[dict[str, Any]] = []
    for intent in INTENTS:
        ranked = sorted(by_intent[intent], key=lambda row: (_rank(str(row["id"])), str(row["id"])))
        selected.extend(ranked[:per_intent])
    component = _components(selected)
    rendered = [_render(row, split=_split(component[str(row["id"])])) for row in selected]
    rendered.sort(key=lambda row: str(row["id"]))
    _write_jsonl(output, rendered)
    split_counts = Counter(str(row["regression_split"]) for row in rendered)
    intent_counts = Counter(str(row["source_assessment"]["intent"]) for row in rendered)
    lineage_splits: dict[str, set[str]] = defaultdict(set)
    template_splits: dict[str, set[str]] = defaultdict(set)
    for row in rendered:
        lineage_splits[str(row["mutation_lineage"])].add(str(row["regression_split"]))
        template_splits[_normalize(str(row["template_family"]))].add(str(row["regression_split"]))
    if any(len(values) != 1 for values in lineage_splits.values()) or any(len(values) != 1 for values in template_splits.values()):
        raise AssertionError("Lineage/template leakage detected while building the corpus.")
    report = {
        "schema_version": "e2b-regression-corpus-v1",
        "rows": len(rendered),
        "per_intent": per_intent,
        "intent_counts": dict(sorted(intent_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "unique_lineages": len(lineage_splits),
        "unique_templates": len(template_splits),
        "source_sha256": {str(path): _sha256(path) for path in proposal_paths},
        "output_sha256": _sha256(output),
        "leakage_checks": {"lineage": True, "template_family": True},
    }
    _write_json(manifest, report)
    return report


def _render(row: Mapping[str, Any], *, split: str) -> dict[str, Any]:
    assessment = row["assessment"]
    function_assessment = {"intent": assessment["intent"], "scores": assessment["scores"]}
    return {
        "id": row["id"],
        "input_text": row["task_text"],
        "source": row["source"],
        "content_sha256": row["content_sha256"],
        "template_family": row["template_family"],
        "mutation_lineage": row["mutation_lineage"],
        "mutation_kind": row["mutation_kind"],
        "regression_split": split,
        "source_assessment": assessment,
        "messages": [
            {"role": "developer", "content": DEVELOPER_INSTRUCTION},
            {"role": "user", "content": row["task_text"]},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {"name": "assess_task", "arguments": function_assessment},
                    }
                ],
            },
        ],
    }


def _components(rows: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    parent = {str(row["id"]): str(row["id"]) for row in rows}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    seen_lineage: dict[str, str] = {}
    seen_template: dict[str, str] = {}
    for row in rows:
        row_id = str(row["id"])
        for value, seen in (
            (str(row["mutation_lineage"]), seen_lineage),
            (_normalize(str(row["template_family"])), seen_template),
        ):
            existing = seen.get(value)
            if existing is None:
                seen[value] = row_id
            else:
                union(row_id, existing)
    return {row_id: find(row_id) for row_id in parent}


def _split(component: str) -> str:
    bucket = int(hashlib.sha256(component.encode("utf-8")).hexdigest()[:8], 16) % 20
    if bucket < 14:
        return "train"
    if bucket < 17:
        return "validation"
    return "test"


def _rank(value: str) -> str:
    return hashlib.sha256(("e2b-regression-corpus-v1\0" + value).encode("utf-8")).hexdigest()


def _validate(row: Mapping[str, Any]) -> None:
    required = {"id", "task_text", "content_sha256", "assessment", "mutation_lineage", "template_family", "mutation_kind", "source"}
    if not required.issubset(row):
        raise ValueError("Proposal row is missing required corpus fields.")
    assessment = row["assessment"]
    if not isinstance(assessment, Mapping) or assessment.get("intent") not in INTENTS or not isinstance(assessment.get("scores"), Mapping):
        raise ValueError("Proposal assessment is invalid.")


def _normalize(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").replace("-", " ").split())


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
