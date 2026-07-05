"""Input and output adapters for evaluator-facing formats."""

from router.adapters.io import (
    load_jsonl_tasks,
    parse_json_task,
    task_from_text,
    write_jsonl_results,
)

__all__ = [
    "load_jsonl_tasks",
    "parse_json_task",
    "task_from_text",
    "write_jsonl_results",
]

