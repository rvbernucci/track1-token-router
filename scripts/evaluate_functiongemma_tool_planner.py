#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from time import monotonic

from router.core.contracts import TaskEnvelope
from router.core.tool_planner import validate_tool_plan_provenance
from router.functiongemma.tool_planner import tool_plan_from_function_call
from router.functiongemma.tooling import generation_eos_token_ids
from router.orchestration.tool_executor import execute_tool_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/functiongemma-tool-planner-v1.json"))
    parser.add_argument("--data", type=Path, default=Path("data/functiongemma-tool-planner-v1"))
    parser.add_argument("--split", choices=("train", "validation", "calibration", "sealed"), required=True)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    config = json.loads(args.config.read_text())
    base = str(args.model or config["model"]["id"])
    revision = None if args.model else config["model"]["revision"]
    tokenizer_source = str(args.adapter or args.model or config["model"]["id"])
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_source, revision=None if args.adapter or args.model else revision)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(base, revision=revision, dtype=torch.bfloat16, device_map={"": 0}, attn_implementation="eager")
    if args.adapter:
        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()
    rows = _rows(args.data / f"{args.split}.jsonl")
    if args.limit:
        rows = _stratified(rows, args.limit)
    predictions = []
    eos = generation_eos_token_ids(tokenizer)
    for offset in range(0, len(rows), args.batch_size):
        batch = rows[offset:offset + args.batch_size]
        conversations = [row["messages"][:2] for row in batch]
        encoded = tokenizer.apply_chat_template(
            conversations, tools=batch[0]["tools"], add_generation_prompt=True,
            return_dict=True, return_tensors="pt", padding=True,
        )
        encoded = {key: value.to(model.device) for key, value in encoded.items()}
        started = monotonic()
        with torch.inference_mode():
            generated = model.generate(
                **encoded, max_new_tokens=160, do_sample=False, use_cache=True,
                pad_token_id=tokenizer.pad_token_id, eos_token_id=eos,
            )
        latency = (monotonic() - started) * 1000 / len(batch)
        prompt_length = encoded["input_ids"].shape[-1]
        for index, row in enumerate(batch):
            tokens = generated[index][prompt_length:].tolist()
            while tokens and tokens[-1] == tokenizer.pad_token_id:
                tokens.pop()
            raw = tokenizer.decode(tokens, skip_special_tokens=False)
            prediction = None
            error = ""
            accepted = False
            final_correct = False
            try:
                plan = tool_plan_from_function_call(raw)
                if plan.tool != "none":
                    plan = validate_tool_plan_provenance(row["messages"][1]["content"], plan)
                    evidence = execute_tool_plan(plan)
                    accepted = True
                    final_correct = evidence.result.replace(",", "") == row["expected_answer"].replace(",", "")
                else:
                    final_correct = row["expected_function"] == "decline_tool"
                prediction = plan.to_dict()
            except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
                error = str(exc)
            predicted_function = "decline_tool" if prediction and prediction["tool"] == "none" else (prediction or {}).get("tool")
            predictions.append({
                "id": row["id"], "family": row["family"], "split": row["split"],
                "expected_function": row["expected_function"], "predicted_function": predicted_function,
                "schema_valid": prediction is not None,
                "tool_correct": predicted_function == row["expected_function"],
                "arguments_exact": bool(prediction and prediction.get("arguments") == row.get("expected_arguments")),
                "accepted": accepted, "final_correct": final_correct,
                "unsafe_false_positive": row["expected_function"] == "decline_tool" and accepted,
                "raw_output": raw, "error": error, "latency_ms": round(latency, 2),
            })
    summary = _summary(predictions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"summary": summary, "rows": predictions}, indent=2) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0


def _summary(rows: list[dict]) -> dict:
    by_family: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_family[row["family"]].append(row)
    accepted = [row for row in rows if row["accepted"]]
    return {
        "tasks": len(rows), "schema_validity": sum(row["schema_valid"] for row in rows) / max(1, len(rows)),
        "tool_accuracy": sum(row["tool_correct"] for row in rows) / max(1, len(rows)),
        "arguments_exact_rate": sum(row["arguments_exact"] for row in rows) / max(1, len(rows)),
        "accepted": len(accepted),
        "supported_precision": sum(row["final_correct"] for row in accepted) / max(1, len(accepted)),
        "unsafe_false_positive_rate": sum(row["unsafe_false_positive"] for row in rows) / max(1, sum(row["expected_function"] == "decline_tool" for row in rows)),
        "mean_latency_ms": round(sum(row["latency_ms"] for row in rows) / max(1, len(rows)), 2),
        "by_family": {family: {
            "tasks": len(items), "tool_correct": sum(row["tool_correct"] for row in items),
            "accepted": sum(row["accepted"] for row in items), "final_correct": sum(row["final_correct"] for row in items),
        } for family, items in sorted(by_family.items())},
    }


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _stratified(rows: list[dict], limit: int) -> list[dict]:
    selected = []
    families = sorted({row["family"] for row in rows})
    for index in range(max(len(rows), limit)):
        family = families[index % len(families)]
        family_rows = [row for row in rows if row["family"] == family]
        candidate = family_rows[(index // len(families)) % len(family_rows)]
        if candidate not in selected:
            selected.append(candidate)
        if len(selected) >= min(limit, len(rows)):
            break
    return selected


if __name__ == "__main__":
    raise SystemExit(main())
