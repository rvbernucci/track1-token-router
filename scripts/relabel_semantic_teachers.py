#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import Intent, SUB_INTENTS_BY_INTENT
from router.dataset_forge.contracts import stable_id
from router.dataset_forge.providers import ProviderError, provider_from_env
from router.dataset_forge.storage import AppendOnlyJsonl


PROMPT_FILES = (
    "reports/generated/amd-pod-e2b-regression-2000/tasks.jsonl",
    "evals/e2b-regression-v2/inputs/train.jsonl",
    "evals/e2b-regression-v2/inputs/validation.jsonl",
    "evals/e2b-regression-v2/inputs/final_holdout.jsonl",
    "evals/e2b-boundary-v1/sealed/tasks.jsonl",
    "evals/e2b-expansion-v1/splits/train.jsonl",
    "evals/e2b-expansion-v1/splits/calibration.jsonl",
    "evals/e2b-expansion-v1/sealed/tasks/final_holdout.jsonl",
)
INTENTS = tuple(intent.value for intent in Intent)
SUB_INTENTS = tuple(sorted({value for values in SUB_INTENTS_BY_INTENT.values() for value in values}))


def main() -> int:
    parser = argparse.ArgumentParser(description="Relabel router semantics with independent teacher models.")
    parser.add_argument("--provider", choices=("agy", "codex", "fireworks"), required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--max-batches", type=int)
    parser.add_argument("--budget-usd", type=float, default=12.0)
    parser.add_argument("--env-file", action="append", type=Path)
    parser.add_argument(
        "--output-root", type=Path, default=Path("reports/generated/semantic-teacher-relabel-v1"),
    )
    parser.add_argument("--output-name", help="Checkpoint filename prefix; defaults to the provider name.")
    parser.add_argument(
        "--completed-from", action="append", type=Path,
        help="Treat task IDs in another teacher checkpoint as completed.",
    )
    args = parser.parse_args()
    _load_env(args.env_file or [Path(".env.dataset-forge.local"), Path(".env.fireworks.local")])
    if args.batch_size < 1 or args.workers < 1:
        parser.error("--batch-size and --workers must be positive")

    ledger = _keyed(_rows(ROOT / "reports/generated/e2b-expansion-v1/regression-ledger.jsonl"), "task_id")
    prompts = _prompt_index()
    missing = sorted(set(ledger) - set(prompts))
    if missing:
        raise ValueError(f"Missing prompt text for {len(missing)} ledger rows.")

    output_root = _absolute(args.output_root)
    output_name = args.output_name or args.provider
    output = AppendOnlyJsonl(output_root / f"{output_name}-batches.jsonl", id_field="batch_id")
    completed = {
        str(item["task_id"])
        for batch in output.read_all()
        for item in batch.get("items", [])
        if isinstance(item, dict) and item.get("task_id")
    }
    for completed_path in args.completed_from or []:
        for batch in _rows(_absolute(completed_path)):
            completed.update(
                str(item["task_id"])
                for item in batch.get("items", [])
                if isinstance(item, dict) and item.get("task_id")
            )
    pending = [task_id for task_id in sorted(ledger) if task_id not in completed]
    batches = [pending[index:index + args.batch_size] for index in range(0, len(pending), args.batch_size)]
    if args.max_batches is not None:
        batches = batches[:args.max_batches]
    provider = provider_from_env(args.provider, role="semantic_router_teacher", max_tokens=args.max_tokens)

    projected = 0.0
    jobs = []
    for task_ids in batches:
        prompt = _teacher_prompt(task_ids, prompts)
        estimate = provider.estimate_upper_bound_usd(prompt) if args.provider == "fireworks" else 0.0
        if projected + estimate > args.budget_usd:
            break
        projected += estimate
        jobs.append((task_ids, prompt))

    completed_batches = 0
    failed_batches = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_invoke, provider, args.provider, task_ids, prompt): task_ids
            for task_ids, prompt in jobs
        }
        for future in as_completed(futures):
            try:
                record = future.result()
                output.append_unique(record)
                completed_batches += 1
            except (ProviderError, ValueError, OSError) as exc:
                failed_batches += 1
                print(json.dumps({"provider": args.provider, "error": str(exc)}, sort_keys=True), file=sys.stderr)

    payload = {
        "provider": args.provider,
        "ledger_rows": len(ledger),
        "previously_completed": len(completed),
        "scheduled_batches": len(jobs),
        "completed_batches": completed_batches,
        "failed_batches": failed_batches,
        "projected_upper_bound_usd": projected,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if failed_batches == 0 else 1


def _invoke(provider: Any, provider_name: str, task_ids: Sequence[str], prompt: str) -> dict[str, Any]:
    invocation = provider.invoke(
        prompt=prompt,
        response_schema=_schema(len(task_ids)),
        role="semantic_router_teacher",
    )
    raw_items = invocation.payload.get("items")
    if not isinstance(raw_items, list) or len(raw_items) != len(task_ids):
        raise ValueError("Teacher returned the wrong item count.")
    items = [_validated_item(item) for item in raw_items]
    returned_ids = [item["task_id"] for item in items]
    if sorted(returned_ids) != sorted(task_ids) or len(set(returned_ids)) != len(task_ids):
        raise ValueError("Teacher returned missing, duplicate, or unexpected task IDs.")
    batch_id = stable_id("semantic-teacher-v1", provider_name, *task_ids)
    return {
        "schema_version": "semantic-teacher-batch-v1",
        "batch_id": batch_id,
        "provider": provider_name,
        "items": sorted(items, key=lambda item: item["task_id"]),
        "provenance": invocation.provenance.to_dict(),
    }


def _teacher_prompt(task_ids: Sequence[str], prompts: Mapping[str, str]) -> str:
    tasks = [{"task_id": task_id, "prompt": prompts[task_id]} for task_id in task_ids]
    return (
        "Classify each quoted task without answering it. Infer semantic demands only; do not count characters, "
        "tokens, code lines, entities, or formatting markers because a deterministic engine handles those.\n"
        "Use these anchors consistently:\n"
        "difficulty: 0 trivial lookup/classification, 1 easy, 2 moderate, 3 hard, 4 expert.\n"
        "reasoning_demand: 0 direct extraction, 5 multi-step ordinary reasoning, 10 expert/deep reasoning.\n"
        "generation_demand: 0 label/exact token, 5 short synthesis, 10 long or complex code/text generation.\n"
        "knowledge_requirement: 0 fully contained in prompt, 5 common stable knowledge, 10 specialized/current/private.\n"
        "ambiguity: 0 one clear interpretation, 10 materially underspecified or conflicting.\n"
        "deterministic_fit: 0 requires judgment/open generation, 10 uniquely solvable by a safe mechanical engine.\n"
        "confidence: 0 uncertain, 100 certain. Select the closest allowed intent and sub_intent.\n\n"
        f"TASKS:\n{json.dumps(tasks, ensure_ascii=False, separators=(',', ':'))}"
    )


def _schema(item_count: int) -> dict[str, Any]:
    score = {"type": "integer", "minimum": 0, "maximum": 10}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "minItems": item_count,
                "maxItems": item_count,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "task_id", "intent", "difficulty", "reasoning_demand",
                        "generation_demand", "knowledge_requirement", "ambiguity",
                        "deterministic_fit", "confidence",
                    ],
                    "properties": {
                        "task_id": {"type": "string"},
                        "intent": {"type": "string", "enum": list(INTENTS)},
                        "difficulty": {"type": "integer", "minimum": 0, "maximum": 4},
                        "reasoning_demand": score,
                        "generation_demand": score,
                        "knowledge_requirement": score,
                        "ambiguity": score,
                        "deterministic_fit": score,
                        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    },
                },
            }
        },
    }


def _validated_item(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Teacher item must be an object.")
    task_id = str(raw.get("task_id") or "")
    intent = str(raw.get("intent") or "")
    sub_intent = str(raw.get("sub_intent") or "")
    if not task_id or intent not in INTENTS:
        raise ValueError("Teacher item has an invalid task_id or intent.")
    allowed_sub_intents = SUB_INTENTS_BY_INTENT[Intent(intent)]
    item = {
        "task_id": task_id,
        "intent": intent,
        "sub_intent": sub_intent if sub_intent in allowed_sub_intents else None,
    }
    for name, upper in (
        ("difficulty", 4), ("reasoning_demand", 10), ("generation_demand", 10),
        ("knowledge_requirement", 10), ("ambiguity", 10), ("deterministic_fit", 10),
        ("confidence", 100),
    ):
        value = raw.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= upper:
            raise ValueError(f"Teacher item has invalid {name}.")
        item[name] = value
    return item


def _prompt_index() -> dict[str, str]:
    result = {}
    for relative in PROMPT_FILES:
        for row in _rows(ROOT / relative):
            task_id = row.get("task_id") or row.get("id")
            prompt = row.get("prompt") or row.get("task_text") or row.get("input_text")
            if isinstance(task_id, str) and isinstance(prompt, str):
                result[task_id] = prompt
    return result


def _load_env(paths: Sequence[Path]) -> None:
    for path in paths:
        resolved = _absolute(path)
        if not resolved.is_file():
            continue
        for line in resolved.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _keyed(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, Mapping[str, Any]]:
    return {str(row[field]): row for row in rows}


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
