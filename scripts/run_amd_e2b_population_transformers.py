#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.core.contracts import TaskEnvelope
from router.core.e2b_runner import E2B_PROMPT_VERSION, build_e2b_messages
from router.orchestration.final_validator import apply_answer_contract
from scripts.run_e2b_contract_population import population


SCHEMA_VERSION = "amd-e2b-population-transformers-v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay the E2B population with Transformers on AMD ROCm.")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-new-tokens", type=int, default=96)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 1 or args.max_new_tokens < 1 or args.limit < 0:
        parser.error("batch size and token limit must be positive; limit cannot be negative")

    import torch
    from transformers import AutoModelForCausalLM, AutoProcessor

    tasks = population(ROOT)
    if args.limit:
        tasks = tasks[: args.limit]
    completed = _completed_ids(args.output) if args.resume else set()
    if args.output.exists() and not args.resume:
        raise ValueError("Output exists; pass --resume to append only missing tasks.")
    pending = [task for task in tasks if task["task_id"] not in completed]
    args.output.parent.mkdir(parents=True, exist_ok=True)

    processor = AutoProcessor.from_pretrained(args.model)
    if getattr(processor, "tokenizer", None) is not None:
        processor.tokenizer.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        dtype=torch.bfloat16,
        device_map={"": 0},
    )
    model.eval()

    written = 0
    for offset in range(0, len(pending), args.batch_size):
        batch = pending[offset : offset + args.batch_size]
        rendered = [
            processor.apply_chat_template(
                build_e2b_messages(task["prompt"]),
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            for task in batch
        ]
        encoded = processor(text=rendered, return_tensors="pt", padding=True).to(model.device)
        input_length = encoded["input_ids"].shape[-1]
        started = perf_counter()
        with torch.inference_mode():
            generated = model.generate(
                **encoded,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                use_cache=True,
                pad_token_id=processor.tokenizer.pad_token_id,
            )
        latency_ms = (perf_counter() - started) * 1000 / len(batch)
        decoded = processor.batch_decode(generated[:, input_length:], skip_special_tokens=False)
        records = [
            _record(task, _parsed_answer(processor, raw), raw, latency_ms)
            for task, raw in zip(batch, decoded, strict=True)
        ]
        with args.output.open("a", encoding="utf-8") as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        written += len(records)
        print(
            json.dumps(
                {
                    "written": written,
                    "remaining": len(pending) - written,
                    "latency_ms_per_task": round(latency_ms, 2),
                    "vram_allocated_mib": round(torch.cuda.memory_allocated() / 2**20, 1),
                },
                sort_keys=True,
            ),
            flush=True,
        )

    print(json.dumps({"population": len(tasks), "resumed": len(completed), "written": written}, sort_keys=True))
    return 0


def _parsed_answer(processor: Any, raw: str) -> str:
    try:
        return _answer(processor.parse_response(raw))
    except (KeyError, TypeError, ValueError):
        # A single unusual Gemma response shape must not discard the full batch.
        return raw.replace("<end_of_turn>", "").strip()


def _answer(parsed: Any) -> str:
    if isinstance(parsed, str):
        return parsed.strip()
    if isinstance(parsed, Mapping):
        for key in ("content", "text", "response"):
            value = parsed.get(key)
            if isinstance(value, str):
                return value.strip()
            if isinstance(value, (Mapping, list)):
                try:
                    nested = _answer(value)
                except ValueError:
                    continue
                if nested:
                    return nested
    if isinstance(parsed, list):
        chunks = []
        for item in parsed:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, (Mapping, list)):
                try:
                    chunks.append(_answer(item))
                except ValueError:
                    continue
        text = "".join(chunks)
        if text.strip():
            return text.strip()
    raise ValueError(f"Unsupported Gemma response shape: {type(parsed).__name__}")


def _record(task: Mapping[str, Any], answer: str, raw: str, latency_ms: float) -> dict[str, Any]:
    envelope = TaskEnvelope(id=str(task["task_id"]), input_text=str(task["prompt"]))
    contract = apply_answer_contract(envelope, answer)
    return {
        **task,
        "schema_version": SCHEMA_VERSION,
        "prompt_sha256": hashlib.sha256(str(task["prompt"]).encode()).hexdigest(),
        "prompt_version": E2B_PROMPT_VERSION,
        "raw_generation": raw,
        "raw_answer": answer,
        "post_contract_answer": contract.answer if contract.valid else answer,
        "answer_contract": contract.to_dict(),
        "latency_ms": round(latency_ms, 2),
        "error": None,
    }


def _completed_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        str(row["task_id"])
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in (json.loads(line),)
    }


if __name__ == "__main__":
    raise SystemExit(main())
