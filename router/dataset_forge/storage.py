from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

try:
    import fcntl
except ImportError:  # pragma: no cover - Linux and macOS both provide fcntl
    fcntl = None  # type: ignore[assignment]


class AppendOnlyJsonl:
    def __init__(self, path: Path, *, id_field: str = "id") -> None:
        self.path = path
        self.id_field = id_field
        self.lock_path = path.with_suffix(path.suffix + ".lock")

    def append_unique(self, record: Mapping[str, Any]) -> bool:
        record_id = record.get(self.id_field)
        if not isinstance(record_id, str) or not record_id:
            raise ValueError(f"Append-only record requires non-empty {self.id_field!r}.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _exclusive_lock(self.lock_path):
            if record_id in self.ids():
                return False
            encoded = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            descriptor = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            try:
                os.write(descriptor, encoded.encode("utf-8"))
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        return True

    def ids(self) -> set[str]:
        if not self.path.exists():
            return set()
        return {
            str(record[self.id_field])
            for record in self.read_all()
            if isinstance(record.get(self.id_field), str)
        }

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        with self.path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Malformed JSONL at {self.path}:{line_no}: {exc}") from exc
                if not isinstance(payload, dict):
                    raise ValueError(f"JSONL row at {self.path}:{line_no} must be an object.")
                records.append(payload)
        return records


class AtomicCheckpoint:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema_version": "dataset-forge-checkpoint-v1",
                "completed_target_ids": [],
                "failed_target_ids": [],
                "fireworks_billable_usd": 0.0,
                "provider_handoffs": 0,
                "batches_completed": 0,
            }
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != "dataset-forge-checkpoint-v1":
            raise ValueError(f"Unsupported checkpoint at {self.path}.")
        return payload

    def save(self, payload: Mapping[str, Any]) -> None:
        record = dict(payload)
        record["schema_version"] = "dataset-forge-checkpoint-v1"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=self.path.name + ".", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(record, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
