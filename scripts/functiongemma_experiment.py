#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from router.core.contracts import TaskAssessment
from router.functiongemma.calibration import fit_ordinal_calibration, load_calibration
from router.functiongemma.metrics import assessment_metrics, boundary_ordering_metrics
from router.functiongemma.tooling import (
    ASSESS_TASK_TOOL,
    DEVELOPER_INSTRUCTION,
    SCORE_FIELDS,
    assessment_from_function_call,
    canonical_sha256,
    file_sha256,
    generation_eos_token_ids,
    jsonl_rows,
    training_conversation,
    validate_training_row,
    write_jsonl,
)


CONFIG_SCHEMA_VERSION = "functiongemma-experiment-v1"
DEFAULT_CONFIG = Path("configs/functiongemma-sprint46.json")
PINNED_ENVIRONMENT = {
    "python": "3.10.12",
    "torch": "2.9.1+gitff65f5b",
    "transformers": "4.57.6",
    "datasets": "4.8.2",
    "accelerate": "1.13.0",
    "peft": "0.18.1",
    "trl": "0.26.2",
}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Reproducible FunctionGemma Sprint 46 experiments.")
    root.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    commands = root.add_subparsers(dest="command", required=True)

    commands.add_parser("doctor")
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--split-root", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)

    train = commands.add_parser("train")
    train.add_argument("--data", type=Path, required=True)
    train.add_argument("--variant", choices=["full_sft", "lora_r8", "lora_r16"], required=True)
    train.add_argument("--output", type=Path, required=True)

    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--model", required=True)
    evaluate.add_argument("--revision")
    evaluate.add_argument("--tasks", type=Path, required=True)
    evaluate.add_argument("--gold", type=Path)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--report", type=Path, required=True)
    evaluate.add_argument("--batch-size", type=int, default=1)

    calibrate = commands.add_parser("calibrate")
    calibrate.add_argument("--predictions", type=Path, required=True)
    calibrate.add_argument("--output", type=Path, required=True)

    boundary = commands.add_parser("boundary")
    boundary.add_argument("--tasks", type=Path, required=True)
    boundary.add_argument("--predictions", type=Path, required=True)
    boundary.add_argument("--calibration", type=Path)
    boundary.add_argument("--output", type=Path, required=True)

    select = commands.add_parser("select")
    select.add_argument("--baseline", type=Path, required=True)
    select.add_argument("--candidate", action="append", type=Path, required=True)
    select.add_argument("--output", type=Path, required=True)

    manifest = commands.add_parser("manifest")
    manifest.add_argument("--artifact", type=Path, required=True)
    manifest.add_argument("--data", type=Path, required=True)
    manifest.add_argument("--calibration", type=Path)
    manifest.add_argument("--runtime", type=Path)
    manifest.add_argument("--environment-report", type=Path)
    manifest.add_argument("--output", type=Path, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    config = load_config(args.config)
    if args.command == "doctor":
        return emit(doctor(config))
    if args.command == "prepare":
        return emit(prepare(config, args.split_root, args.output))
    if args.command == "train":
        return emit(train(config, args.data, args.variant, args.output))
    if args.command == "evaluate":
        return emit(
            evaluate(
                config,
                args.model,
                args.revision,
                args.tasks,
                args.gold,
                args.output,
                args.report,
                batch_size=args.batch_size,
            )
        )
    if args.command == "calibrate":
        return emit(calibrate(args.predictions, args.output))
    if args.command == "boundary":
        return emit(boundary_report(args.tasks, args.predictions, args.calibration, args.output))
    if args.command == "select":
        return emit(select(args.baseline, args.candidate, args.output))
    if args.command == "manifest":
        return emit(
            manifest(
                config,
                args.config,
                args.artifact,
                args.data,
                args.calibration,
                args.runtime,
                args.environment_report,
                args.output,
            )
        )
    return 2


def load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise ValueError("Unsupported FunctionGemma experiment configuration.")
    _exact(payload, {"schema_version", "model", "environment", "data", "generation", "variants"}, "config")
    model = _mapping(payload["model"], "model")
    _exact(model, {"id", "revision"}, "model")
    if model["id"] != "google/functiongemma-270m-it" or not _sha(model["revision"]):
        raise ValueError("FunctionGemma model ID and immutable revision are required.")
    environment = _mapping(payload["environment"], "environment")
    environment_fields = {"python", "torch", "transformers", "datasets", "accelerate", "peft", "trl"}
    _exact(environment, environment_fields, "environment")
    if dict(environment) != PINNED_ENVIRONMENT:
        raise ValueError("Experiment environment must match the measured and pinned AMD ROCm stack.")
    data = _mapping(payload["data"], "data")
    _exact(data, {"max_length", "seed"}, "data")
    _integer(data["max_length"], 128, 2048, "data.max_length")
    _integer(data["seed"], 0, 2**31 - 1, "data.seed")
    generation = _mapping(payload["generation"], "generation")
    _exact(generation, {"max_new_tokens"}, "generation")
    _integer(generation["max_new_tokens"], 32, 256, "generation.max_new_tokens")
    variants = _mapping(payload["variants"], "variants")
    _exact(variants, {"full_sft", "lora_r8", "lora_r16"}, "variants")
    for name, value in variants.items():
        _validate_variant(name, _mapping(value, f"variants.{name}"))
    return payload


def doctor(config: Mapping[str, Any]) -> dict[str, Any]:
    packages: dict[str, str | None] = {}
    for package in ("torch", "transformers", "datasets", "accelerate", "trl", "peft", "safetensors"):
        try:
            module = __import__(package)
            packages[package] = getattr(module, "__version__", "unknown")
        except ImportError:
            packages[package] = None
    gpu: dict[str, Any] = {"available": False}
    try:
        import torch

        gpu = {
            "available": torch.cuda.is_available(),
            "torch": torch.__version__,
            "hip": torch.version.hip,
            "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "bf16": torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False,
        }
    except ImportError:
        pass
    observed_environment = {
        "python": platform.python_version(),
        **{name: packages[name] for name in ("torch", "transformers", "datasets", "accelerate", "peft", "trl")},
    }
    expected_environment = dict(_mapping(config["environment"], "environment"))
    mismatches = {
        name: {"expected": expected_environment[name], "observed": observed_environment[name]}
        for name in expected_environment
        if observed_environment[name] != expected_environment[name]
    }
    return {
        "schema_version": "functiongemma-doctor-v1",
        "python": sys.version,
        "platform": platform.platform(),
        "config_sha256": canonical_sha256(config),
        "expected_environment": expected_environment,
        "observed_environment": observed_environment,
        "environment_matches": not mismatches,
        "environment_mismatches": mismatches,
        "packages": packages,
        "gpu": gpu,
    }


def prepare(config: Mapping[str, Any], split_root: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    hashes: dict[str, str] = {}
    for split in ("train", "validation"):
        source = split_root / f"{split}.jsonl"
        rows = jsonl_rows(source)
        prepared: list[dict[str, Any]] = []
        for row in rows:
            messages = row.get("messages")
            if not isinstance(messages, list) or len(messages) != 3:
                raise ValueError("Prepared source row must contain three messages.")
            task_text = messages[1].get("content") if isinstance(messages[1], Mapping) else None
            assistant = messages[2] if isinstance(messages[2], Mapping) else {}
            calls = assistant.get("tool_calls")
            if not isinstance(task_text, str) or not isinstance(calls, list) or len(calls) != 1:
                raise ValueError("Prepared source row is missing its task or gold assessment.")
            function = calls[0].get("function") if isinstance(calls[0], Mapping) else None
            if not isinstance(function, Mapping) or not isinstance(function.get("arguments"), Mapping):
                raise ValueError("Prepared source row has malformed gold arguments.")
            gold = TaskAssessment.from_mapping(function["arguments"])
            metadata = {key: value for key, value in row.items() if key not in {"messages", "tools"}}
            prepared_row = {**metadata, **training_conversation(task_text, gold)}
            validate_training_row(prepared_row)
            prepared.append(prepared_row)
        destination = output / f"{split}.jsonl"
        write_jsonl(destination, prepared)
        counts[split] = len(prepared)
        hashes[split] = file_sha256(destination)
    manifest_payload = {
        "schema_version": "functiongemma-prepared-data-v1",
        "config_sha256": canonical_sha256(config),
        "tool_sha256": canonical_sha256(ASSESS_TASK_TOOL),
        "counts": counts,
        "sha256": hashes,
    }
    write_json(output / "manifest.json", manifest_payload)
    return manifest_payload


def train(config: Mapping[str, Any], data: Path, variant_name: str, output: Path) -> dict[str, Any]:
    environment_report = doctor(config)
    if not environment_report["environment_matches"]:
        raise RuntimeError(f"AMD training environment mismatch: {environment_report['environment_mismatches']}")
    import torch
    from datasets import Dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed
    from trl import SFTConfig, SFTTrainer

    variant = _mapping(_mapping(config["variants"], "variants")[variant_name], variant_name)
    model_config = _mapping(config["model"], "model")
    set_seed(int(_mapping(config["data"], "data")["seed"]))
    tokenizer = AutoTokenizer.from_pretrained(model_config["id"], revision=model_config["revision"])
    model = AutoModelForCausalLM.from_pretrained(
        model_config["id"],
        revision=model_config["revision"],
        dtype="auto",
        attn_implementation="eager",
    )
    if variant["method"] == "lora":
        from peft import LoraConfig, TaskType, get_peft_model

        lora = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=int(variant["rank"]),
            lora_alpha=int(variant["alpha"]),
            lora_dropout=0.05,
            bias="none",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        )
        model = get_peft_model(model, lora)
    train_rows = jsonl_rows(data / "train.jsonl")
    validation_rows = jsonl_rows(data / "validation.jsonl")
    args = SFTConfig(
        output_dir=str(output / "checkpoints"),
        max_length=int(_mapping(config["data"], "data")["max_length"]),
        packing=False,
        num_train_epochs=int(variant["epochs"]),
        per_device_train_batch_size=int(variant["batch_size"]),
        per_device_eval_batch_size=int(variant["batch_size"]),
        gradient_accumulation_steps=int(variant["gradient_accumulation_steps"]),
        learning_rate=float(variant["learning_rate"]),
        warmup_ratio=0.1,
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        bf16=bool(torch.cuda.is_available() and torch.cuda.is_bf16_supported()),
        fp16=bool(torch.cuda.is_available() and not torch.cuda.is_bf16_supported()),
        optim="adamw_torch_fused" if torch.cuda.is_available() else "adamw_torch",
        report_to="none",
        logging_steps=1,
        seed=int(_mapping(config["data"], "data")["seed"]),
    )
    trainer = SFTTrainer(
        model=model,
        args=args,
        train_dataset=Dataset.from_list(train_rows),
        eval_dataset=Dataset.from_list(validation_rows),
        processing_class=tokenizer,
    )
    started = time.monotonic()
    result = trainer.train()
    output.mkdir(parents=True, exist_ok=True)
    if variant["method"] == "lora":
        model = model.merge_and_unload()
    model.save_pretrained(output / "model", safe_serialization=True)
    tokenizer.save_pretrained(output / "model")
    report = {
        "schema_version": "functiongemma-training-run-v1",
        "variant": variant_name,
        "variant_config": dict(variant),
        "base_model": dict(model_config),
        "config_sha256": canonical_sha256(config),
        "data_manifest_sha256": file_sha256(data / "manifest.json"),
        "elapsed_seconds": time.monotonic() - started,
        "train_metrics": result.metrics,
        "log_history": trainer.state.log_history,
        "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    }
    write_json(output / "training-report.json", report)
    return {key: report[key] for key in ("variant", "elapsed_seconds", "peak_rss_mb")}


def evaluate(
    config: Mapping[str, Any],
    model_path: str,
    revision: str | None,
    tasks_path: Path,
    gold_path: Path | None,
    output: Path,
    report_path: Path,
    *,
    batch_size: int = 1,
) -> dict[str, Any]:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if batch_size < 1:
        raise ValueError("Evaluation batch size must be positive.")
    tasks = jsonl_rows(tasks_path)
    gold_by_id = _gold(tasks, gold_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path, revision=revision)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        revision=revision,
        dtype="auto",
        attn_implementation="eager",
        device_map="auto",
    )
    model.eval()
    eos_token_ids = generation_eos_token_ids(tokenizer)
    predictions: list[dict[str, Any]] = []
    latencies: list[float] = []
    max_new_tokens = int(_mapping(config["generation"], "generation")["max_new_tokens"])
    for task_batch in _chunks(tasks, batch_size):
        examples = [_task(row) for row in task_batch]
        conversations = [
            [
                {"role": "developer", "content": DEVELOPER_INSTRUCTION},
                {"role": "user", "content": task_text},
            ]
            for _, task_text in examples
        ]
        encoded = tokenizer.apply_chat_template(
            conversations,
            tools=[ASSESS_TASK_TOOL],
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
            padding=True,
        )
        encoded = {key: value.to(model.device) for key, value in encoded.items()}
        started = time.monotonic()
        with torch.inference_mode():
            generated = model.generate(
                **encoded,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                use_cache=True,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=eos_token_ids,
            )
        batch_latency = (time.monotonic() - started) * 1000
        latency = batch_latency / len(task_batch)
        latencies.extend([latency] * len(task_batch))
        prompt_length = encoded["input_ids"].shape[-1]
        for index, (example_id, _) in enumerate(examples):
            raw = tokenizer.decode(generated[index][prompt_length:], skip_special_tokens=False)
            prediction = None
            error = None
            try:
                prediction = assessment_from_function_call(raw).to_dict()
            except ValueError as exc:
                error = str(exc)
            predictions.append(
                {
                    "id": example_id,
                    "gold": gold_by_id[example_id],
                    "prediction": prediction,
                    "raw_output": raw,
                    "parse_error": error,
                    "latency_ms": latency,
                    "input_tokens": int(encoded["attention_mask"][index].sum().item()),
                    "output_tokens": int(generated.shape[-1] - prompt_length),
                }
            )
    write_jsonl(output, predictions)
    metrics = assessment_metrics(predictions)
    metrics.update(
        {
            "model": model_path,
            "revision": revision,
            "batch_size": batch_size,
            "throughput_tasks_per_second": 1000.0 / percentile(latencies, 0.50),
            "p50_latency_ms": percentile(latencies, 0.50),
            "p95_latency_ms": percentile(latencies, 0.95),
            "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            "predictions_sha256": file_sha256(output),
        }
    )
    write_json(report_path, metrics)
    return metrics


def calibrate(predictions_path: Path, output: Path) -> dict[str, Any]:
    all_rows = jsonl_rows(predictions_path)
    rows = [row for row in all_rows if row.get("prediction") is not None]
    if len(rows) != len(all_rows):
        raise ValueError("Calibration requires every validation prediction to pass the exact assessment schema.")
    result: dict[str, Any] = {
        "schema_version": "functiongemma-score-calibration-v1",
        "source_sha256": file_sha256(predictions_path),
        "dimensions": {},
    }
    for name in SCORE_FIELDS:
        pairs = [
            (int(row["prediction"]["scores"][name]), int(row["gold"]["scores"][name]))
            for row in rows
        ]
        result["dimensions"][name] = fit_ordinal_calibration(pairs).to_dict()
    write_json(output, result)
    return result


def boundary_report(
    tasks_path: Path,
    predictions_path: Path,
    calibration_path: Path | None,
    output: Path,
) -> dict[str, Any]:
    tasks = jsonl_rows(tasks_path)
    predictions = jsonl_rows(predictions_path)
    result = {
        "schema_version": "functiongemma-boundary-report-v1",
        "tasks_sha256": file_sha256(tasks_path),
        "predictions_sha256": file_sha256(predictions_path),
        "calibration_sha256": file_sha256(calibration_path) if calibration_path else None,
        "raw": boundary_ordering_metrics(tasks, predictions),
        "calibrated": None,
    }
    if calibration_path:
        bundle = load_calibration(calibration_path)
        calibrated: list[dict[str, Any]] = []
        for row in predictions:
            prediction = row.get("prediction")
            calibrated.append(
                {
                    **row,
                    "prediction": (
                        bundle.apply(TaskAssessment.from_mapping(prediction)).to_dict()
                        if isinstance(prediction, Mapping)
                        else None
                    ),
                }
            )
        result["calibrated"] = boundary_ordering_metrics(tasks, calibrated)
    write_json(output, result)
    return result


def select(baseline_path: Path, candidate_paths: list[Path], output: Path) -> dict[str, Any]:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    candidates = [json.loads(path.read_text(encoding="utf-8")) for path in candidate_paths]
    ranked: list[dict[str, Any]] = []
    for candidate, path in zip(candidates, candidate_paths):
        score_improvements = {
            name: float(baseline["score_mae"][name]) - float(candidate["score_mae"][name])
            for name in SCORE_FIELDS
        }
        promoted = (
            candidate["schema_validity"] >= 0.999
            and candidate["intent_accuracy"] >= baseline["intent_accuracy"]
            and all(value > 0 for value in score_improvements.values())
        )
        ranked.append(
            {
                "path": str(path),
                "model": candidate.get("model"),
                "promoted": promoted,
                "score_improvements": score_improvements,
                "intent_accuracy": candidate["intent_accuracy"],
                "mean_score_mae": sum(candidate["score_mae"].values()) / len(SCORE_FIELDS),
            }
        )
    ranked.sort(key=lambda item: (not item["promoted"], -item["intent_accuracy"], item["mean_score_mae"]))
    result = {
        "schema_version": "functiongemma-selection-v1",
        "baseline_sha256": file_sha256(baseline_path),
        "ranking": ranked,
        "champion": ranked[0]["model"] if ranked and ranked[0]["promoted"] else None,
    }
    write_json(output, result)
    return result


def manifest(
    config: Mapping[str, Any],
    config_path: Path,
    artifact: Path,
    data: Path,
    calibration_path: Path | None,
    runtime_path: Path | None,
    environment_report_path: Path | None,
    output: Path,
) -> dict[str, Any]:
    files = sorted(path for path in artifact.rglob("*") if path.is_file())
    result = {
        "schema_version": "functiongemma-artifact-manifest-v1",
        "model": dict(_mapping(config["model"], "model")),
        "config_sha256": file_sha256(config_path),
        "data_manifest_sha256": file_sha256(data / "manifest.json"),
        "tool_sha256": canonical_sha256(ASSESS_TASK_TOOL),
        "calibration_sha256": file_sha256(calibration_path) if calibration_path else None,
        "runtime_sha256": file_sha256(runtime_path) if runtime_path else None,
        "runtime": json.loads(runtime_path.read_text(encoding="utf-8")) if runtime_path else None,
        "artifact_files": {str(path.relative_to(artifact)): file_sha256(path) for path in files},
        "environment_report_sha256": (
            file_sha256(environment_report_path) if environment_report_path else None
        ),
        "environment": (
            json.loads(environment_report_path.read_text(encoding="utf-8"))
            if environment_report_path
            else doctor(config)
        ),
        "git_commit": _git_commit(),
        "git_dirty": _git_dirty(),
    }
    write_json(output, result)
    return result


def _gold(tasks: list[dict[str, Any]], gold_path: Path | None) -> dict[str, dict[str, Any]]:
    if gold_path:
        result = {row["id"]: TaskAssessment.from_mapping(row["assessment"]).to_dict() for row in jsonl_rows(gold_path)}
        task_ids = {str(row["id"]) for row in tasks}
        if set(result) != task_ids:
            raise ValueError("Hidden task IDs and private gold IDs must match exactly.")
        return result
    result: dict[str, dict[str, Any]] = {}
    for row in tasks:
        result[str(row["id"])] = validate_training_row(row).to_dict()
    return result


def _task(row: Mapping[str, Any]) -> tuple[str, str]:
    if "input_text" in row:
        return str(row["id"]), str(row["input_text"])
    messages = row.get("messages")
    if isinstance(messages, list) and len(messages) >= 2:
        return str(row["id"]), str(messages[1]["content"])
    raise ValueError("Evaluation task has no input text.")


def _chunks(rows: Sequence[dict[str, Any]], size: int) -> Sequence[Sequence[dict[str, Any]]]:
    return [rows[index : index + size] for index in range(0, len(rows), size)]


def _validate_variant(name: str, value: Mapping[str, Any]) -> None:
    common = {"method", "epochs", "learning_rate", "batch_size", "gradient_accumulation_steps"}
    expected = common if name == "full_sft" else common | {"rank", "alpha"}
    _exact(value, expected, name)
    expected_method = "full" if name == "full_sft" else "lora"
    if value["method"] != expected_method:
        raise ValueError(f"{name}.method must be {expected_method!r}.")
    _integer(value["epochs"], 1, 100, f"{name}.epochs")
    _integer(value["batch_size"], 1, 128, f"{name}.batch_size")
    _integer(value["gradient_accumulation_steps"], 1, 128, f"{name}.gradient_accumulation_steps")
    if isinstance(value["learning_rate"], bool) or not isinstance(value["learning_rate"], (int, float)) or not 0 < value["learning_rate"] <= 0.01:
        raise ValueError(f"{name}.learning_rate is invalid.")
    if name != "full_sft":
        if value["rank"] not in {8, 16}:
            raise ValueError(f"{name}.rank must be 8 or 16.")
        _integer(value["alpha"], 1, 128, f"{name}.alpha")


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object.")
    return value


def _exact(value: Mapping[str, Any], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} fields mismatch: expected {sorted(expected)}, got {sorted(value)}.")


def _integer(value: Any, minimum: int, maximum: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}].")


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(character in "0123456789abcdef" for character in value)


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def emit(payload: Mapping[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def _git_commit() -> str | None:
    completed = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else None


def _git_dirty() -> bool | None:
    completed = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=False)
    return bool(completed.stdout) if completed.returncode == 0 else None


if __name__ == "__main__":
    raise SystemExit(main())
