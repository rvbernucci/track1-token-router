from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from router.core.contracts import TaskAssessment
from router.dataset_forge.contracts import content_sha256, stable_id, utc_now
from router.dataset_forge.pipeline import ForgePaths
from router.dataset_forge.storage import AppendOnlyJsonl


HIDDEN_SEED_SCHEMA_VERSION = "teacher-blind-hidden-v1"


def import_hidden_seed(paths: ForgePaths, input_path: Path) -> dict[str, int]:
    store = AppendOnlyJsonl(paths.root / "private" / "hidden-seed.jsonl")
    written = 0
    validated = 0
    for line_no, line in enumerate(input_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        record = validate_hidden_seed_input(payload, line_no=line_no)
        validated += 1
        if store.append_unique(record):
            written += 1
    return {"validated": validated, "written": written}


def validate_hidden_seed_input(payload: Any, *, line_no: int = 0) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"Hidden seed line {line_no} must be an object.")
    expected = {
        "id",
        "task_text",
        "assessment",
        "template_family",
        "mutation_lineage",
        "language",
        "evidence",
        "author",
    }
    if set(payload) != expected:
        raise ValueError(
            f"Hidden seed line {line_no} fields mismatch: "
            f"missing={sorted(expected - set(payload))}, additional={sorted(set(payload) - expected)}."
        )
    for name in expected - {"assessment"}:
        if not isinstance(payload[name], str) or not payload[name].strip():
            raise ValueError(f"Hidden seed {name} must be a non-empty string.")
    assessment = TaskAssessment.from_mapping(payload["assessment"])
    return {
        "schema_version": HIDDEN_SEED_SCHEMA_VERSION,
        "id": payload["id"],
        "task_text": payload["task_text"].strip(),
        "assessment": assessment.to_dict(),
        "template_family": payload["template_family"].strip(),
        "mutation_lineage": payload["mutation_lineage"].strip(),
        "language": payload["language"].strip(),
        "evidence": payload["evidence"].strip(),
        "author": payload["author"].strip(),
        "content_sha256": content_sha256(payload["task_text"]),
        "created_at": utc_now(),
        "review_id": stable_id(
            "hidden_review",
            payload["id"],
            assessment.to_json(),
            payload["evidence"],
            payload["author"],
        ),
    }


def load_hidden_seed(paths: ForgePaths) -> list[dict[str, Any]]:
    records = AppendOnlyJsonl(paths.root / "private" / "hidden-seed.jsonl").read_all()
    expected = {
        "schema_version",
        "id",
        "task_text",
        "assessment",
        "template_family",
        "mutation_lineage",
        "language",
        "evidence",
        "author",
        "content_sha256",
        "created_at",
        "review_id",
    }
    for record in records:
        if set(record) != expected or record.get("schema_version") != HIDDEN_SEED_SCHEMA_VERSION:
            raise ValueError("Invalid teacher-blind hidden seed record.")
        TaskAssessment.from_mapping(record["assessment"])
        if record["content_sha256"] != content_sha256(record["task_text"]):
            raise ValueError("Teacher-blind hidden seed content hash mismatch.")
    return records
