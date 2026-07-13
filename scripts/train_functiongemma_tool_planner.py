#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import resource
from time import monotonic


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/functiongemma-tool-planner-v1.json"))
    parser.add_argument("--data", type=Path, default=Path("data/functiongemma-tool-planner-v1"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=float)
    parser.add_argument("--gradient-accumulation-steps", type=int)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--rank", type=int)
    parser.add_argument("--eval-strategy", choices=("epoch", "no"), default="epoch")
    parser.add_argument("--max-train-rows", type=int, default=0)
    parser.add_argument("--max-validation-rows", type=int, default=0)
    args = parser.parse_args()
    _reject_sealed_training_path(args.data)
    config = json.loads(args.config.read_text())
    _validate_config(config)

    import torch
    from datasets import Dataset
    from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, set_seed
    from trl import SFTConfig, SFTTrainer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for FunctionGemma planner training.")
    seed = int(config["dataset"]["seed"])
    set_seed(seed)
    train_rows = _rows(args.data / "train.jsonl")
    validation_rows = _rows(args.data / "validation.jsonl")
    if args.max_train_rows:
        train_rows = _stratified(train_rows, args.max_train_rows)
    if args.max_validation_rows:
        validation_rows = _stratified(validation_rows, args.max_validation_rows)

    model_config = config["model"]
    qlora = config["qlora"]
    tokenizer = AutoTokenizer.from_pretrained(model_config["id"], revision=model_config["revision"])
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type=qlora["quantization"],
        bnb_4bit_use_double_quant=bool(qlora["double_quantization"]),
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_config["id"], revision=model_config["revision"],
        quantization_config=quantization, device_map={"": 0}, attn_implementation="eager",
    )
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(model, LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=int(args.rank or qlora["rank"]), lora_alpha=int(qlora["alpha"]),
        lora_dropout=float(qlora["dropout"]), bias="none",
        target_modules=list(qlora["target_modules"]),
    ))
    args.output.mkdir(parents=True, exist_ok=True)
    evaluate = args.eval_strategy != "no"
    training_args = SFTConfig(
        output_dir=str(args.output / "checkpoints"),
        max_length=int(config["dataset"]["max_length"]), packing=False, completion_only_loss=True,
        num_train_epochs=float(args.epochs or qlora["epochs"]),
        per_device_train_batch_size=int(qlora["batch_size"]),
        per_device_eval_batch_size=int(qlora["batch_size"]),
        gradient_accumulation_steps=int(args.gradient_accumulation_steps or qlora["gradient_accumulation_steps"]),
        learning_rate=float(args.learning_rate or qlora["learning_rate"]), warmup_ratio=float(qlora["warmup_ratio"]),
        weight_decay=float(qlora["weight_decay"]), lr_scheduler_type="cosine",
        eval_strategy=args.eval_strategy, save_strategy="epoch", save_total_limit=2,
        load_best_model_at_end=evaluate, metric_for_best_model="eval_loss" if evaluate else None,
        greater_is_better=False if evaluate else None,
        bf16=True, gradient_checkpointing=True, optim="paged_adamw_8bit",
        report_to="none", logging_steps=5, seed=seed,
    )
    trainer = SFTTrainer(
        model=model, args=training_args,
        train_dataset=Dataset.from_list(_completion_rows(train_rows)),
        eval_dataset=Dataset.from_list(_completion_rows(validation_rows)) if evaluate else None,
        processing_class=tokenizer,
    )
    started = monotonic()
    result = trainer.train()
    adapter_dir = args.output / "adapter"
    trainer.model.save_pretrained(adapter_dir, safe_serialization=True)
    tokenizer.save_pretrained(adapter_dir)
    report = {
        "schema_version": "functiongemma-tool-planner-training-v1",
        "base_model": model_config, "qlora": qlora,
        "train_rows": len(train_rows), "validation_rows": len(validation_rows),
        "epochs": float(args.epochs or qlora["epochs"]),
        "completion_only_loss": True,
        "gradient_accumulation_steps": training_args.gradient_accumulation_steps,
        "learning_rate": training_args.learning_rate,
        "rank": int(args.rank or qlora["rank"]),
        "eval_strategy": args.eval_strategy,
        "elapsed_seconds": monotonic() - started,
        "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "peak_cuda_allocated_mb": torch.cuda.max_memory_allocated() / 1024**2,
        "peak_cuda_reserved_mb": torch.cuda.max_memory_reserved() / 1024**2,
        "metrics": result.metrics, "log_history": trainer.state.log_history,
        "environment": {
            "python": os.sys.version, "torch": torch.__version__,
            "cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(0),
        },
    }
    (args.output / "training-report.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps({key: report[key] for key in ("train_rows", "validation_rows", "epochs", "elapsed_seconds", "peak_cuda_allocated_mb")}))
    return 0


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _completion_rows(rows: list[dict]) -> list[dict]:
    converted = []
    for row in rows:
        messages = row.get("messages")
        if not isinstance(messages, list) or len(messages) != 3 or messages[-1].get("role") != "assistant":
            raise ValueError("Planner training rows require developer, user and assistant messages.")
        converted.append({
            "prompt": messages[:-1],
            "completion": messages[-1:],
            "tools": row["tools"],
        })
    return converted


def _stratified(rows: list[dict], limit: int) -> list[dict]:
    families = sorted({row["family"] for row in rows})
    selected = []
    while len(selected) < min(limit, len(rows)):
        changed = False
        for family in families:
            candidate = next((row for row in rows if row["family"] == family and row not in selected), None)
            if candidate is not None and len(selected) < limit:
                selected.append(candidate)
                changed = True
        if not changed:
            break
    return selected


def _validate_config(config: dict) -> None:
    if config.get("schema_version") != "functiongemma-tool-planner-config-v1":
        raise ValueError("Unsupported planner training config.")
    revision = config.get("model", {}).get("revision", "")
    if len(revision) != 40 or any(char not in "0123456789abcdef" for char in revision):
        raise ValueError("An immutable base-model revision is required.")


def _reject_sealed_training_path(data: Path) -> None:
    if any(part.casefold() == "sealed" for part in data.parts):
        raise ValueError("The sealed split cannot be used as a training data root.")


if __name__ == "__main__":
    raise SystemExit(main())
