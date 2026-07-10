from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from router.dataset_forge.contracts import DatasetProposal, GoldAssessment
from router.dataset_forge.pipeline import ForgePaths
from router.dataset_forge.hidden_seed import load_hidden_seed
from router.dataset_forge.storage import AppendOnlyJsonl


def build_splits(paths: ForgePaths) -> dict[str, Any]:
    proposals = {
        item.id: item
        for item in (
            DatasetProposal.from_mapping(payload)
            for payload in AppendOnlyJsonl(paths.deduped_proposals).read_all()
        )
    }
    gold_history = [
        GoldAssessment.from_mapping(payload)
        for payload in AppendOnlyJsonl(paths.root / "adjudicated" / "gold.jsonl").read_all()
    ]
    latest_gold: dict[str, GoldAssessment] = {}
    for item in gold_history:
        current = latest_gold.get(item.example_id)
        if current is None or item.revision > current.revision:
            latest_gold[item.example_id] = item
    gold = [item for item in latest_gold.values() if item.adjudication_status == "accepted"]
    private_hidden = load_hidden_seed(paths)
    accepted_pairs: list[tuple[DatasetProposal, GoldAssessment]] = []
    for label in sorted(gold, key=lambda item: item.example_id):
        proposal = proposals.get(label.example_id)
        if proposal is None:
            raise ValueError(f"Gold label references missing proposal {label.example_id!r}.")
        accepted_pairs.append((proposal, label))
    component_by_example = _component_groups([proposal for proposal, _label in accepted_pairs])
    teacher_templates = {_normalize_template(proposal.template_family) for proposal, _label in accepted_pairs}
    teacher_lineages = {proposal.mutation_lineage for proposal, _label in accepted_pairs}
    for hidden in private_hidden:
        if _normalize_template(hidden["template_family"]) in teacher_templates:
            raise ValueError(f"Hidden template collides with teacher data: {hidden['template_family']!r}.")
        if hidden["mutation_lineage"] in teacher_lineages:
            raise ValueError(f"Hidden lineage collides with teacher data: {hidden['mutation_lineage']!r}.")
    hidden_components = {
        component_by_example[proposal.id]
        for proposal, _label in accepted_pairs
        if proposal.source == "codex_hidden_seed"
    }

    assignments: dict[str, str] = {}
    rows: dict[str, list[tuple[DatasetProposal, GoldAssessment]]] = defaultdict(list)
    group_assignments: dict[str, str] = {}
    for proposal, label in accepted_pairs:
        group = component_by_example[proposal.id]
        split = group_assignments.setdefault(
            group,
            "hidden_test" if group in hidden_components else _assign_split(group),
        )
        assignments[proposal.id] = split
        rows[split].append((proposal, label))
    for item in private_hidden:
        assignments[item["id"]] = "hidden_test"
        group_assignments[f"private:{item['mutation_lineage']}"] = "hidden_test"

    split_root = paths.root / "splits"
    _atomic_jsonl(split_root / "train.jsonl", (_training_row(*item) for item in rows["train"]))
    _atomic_jsonl(split_root / "validation.jsonl", (_training_row(*item) for item in rows["validation"]))
    _atomic_jsonl(
        split_root / "hidden_test_tasks.jsonl",
        (
            [
                {"id": proposal.id, "input_text": proposal.task_text}
                for proposal, _label in rows["hidden_test"]
            ]
            + [{"id": item["id"], "input_text": item["task_text"]} for item in private_hidden]
        ),
    )
    _atomic_jsonl(
        paths.root / "private" / "hidden_test_gold.jsonl",
        (
            [
                {"id": proposal.id, "assessment": label.assessment.to_dict()}
                for proposal, label in rows["hidden_test"]
            ]
            + [{"id": item["id"], "assessment": item["assessment"]} for item in private_hidden]
        ),
    )
    manifest = {
        "schema_version": "assessment-splits-v1",
        "counts": {
            "train": len(rows["train"]),
            "validation": len(rows["validation"]),
            "hidden_test": len(rows["hidden_test"]) + len(private_hidden),
        },
        "assignments": assignments,
        "groups": group_assignments,
        "teacher_blind_hidden_only": True,
        "private_hidden_ids": [item["id"] for item in private_hidden],
    }
    _atomic_json(split_root / "manifest.json", manifest)
    return manifest


def _assign_split(group: str) -> str:
    bucket = int(hashlib.sha256(group.encode("utf-8")).hexdigest()[:8], 16) % 10
    return "validation" if bucket == 0 else "train"


def _component_groups(proposals: list[DatasetProposal]) -> dict[str, str]:
    parent = {proposal.id: proposal.id for proposal in proposals}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    seen_lineage: dict[str, str] = {}
    seen_template: dict[str, str] = {}
    for proposal in proposals:
        for value, seen in (
            (proposal.mutation_lineage, seen_lineage),
            (_normalize_template(proposal.template_family), seen_template),
        ):
            existing = seen.get(value)
            if existing is None:
                seen[value] = proposal.id
            else:
                union(proposal.id, existing)
    return {proposal.id: find(proposal.id) for proposal in proposals}


def _normalize_template(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").replace("-", " ").split())


def _training_row(proposal: DatasetProposal, label: GoldAssessment) -> dict[str, Any]:
    return {
        "id": proposal.id,
        "source": proposal.source,
        "template_family": proposal.template_family,
        "mutation_lineage": proposal.mutation_lineage,
        "parent_id": proposal.parent_id,
        "mutation_kind": proposal.mutation_kind,
        "boundary_dimension": proposal.boundary_dimension,
        "boundary_anchor": proposal.boundary_anchor,
        "messages": [
            {
                "role": "developer",
                "content": "Call assess_task exactly once. Assess the task; never answer it or select an engine.",
            },
            {"role": "user", "content": proposal.task_text},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "assess_task",
                            "arguments": label.assessment.to_dict(),
                        },
                    }
                ],
            },
        ],
    }


def _atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
