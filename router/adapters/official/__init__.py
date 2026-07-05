"""Official kickoff adapter templates."""

from router.adapters.official.base import OfficialAdapter
from router.adapters.official.file_payload import FilePayloadAdapter
from router.adapters.official.json_task import JsonTaskAdapter
from router.adapters.official.jsonl_batch import JsonlBatchAdapter
from router.adapters.official.plain_text import PlainTextAdapter

ADAPTERS: dict[str, OfficialAdapter] = {
    "plain_text": PlainTextAdapter(),
    "json_task": JsonTaskAdapter(),
    "jsonl_batch": JsonlBatchAdapter(),
    "file_payload": FilePayloadAdapter(),
}


def get_adapter(name: str) -> OfficialAdapter:
    try:
        return ADAPTERS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown official adapter: {name}") from exc


__all__ = [
    "ADAPTERS",
    "FilePayloadAdapter",
    "JsonTaskAdapter",
    "JsonlBatchAdapter",
    "OfficialAdapter",
    "PlainTextAdapter",
    "get_adapter",
]
